from google.genai.errors import ClientError
from google import genai
from dto import AIAnalysis, JobPriority
from exceptions import RateLimitError
from literals import SYSTEM_INSTRUCTION, SCHEMA_EXPLANATION, SCHEMA_CONFIDENCE, TARGET_TECHNOLOGIES
import asyncio
import logging
import textwrap
from scraper_engine import Scraper, Factory
from groq import AsyncGroq
from groq import RateLimitError as GroqRateLimitError
from pydantic import BaseModel, Field, ConfigDict
from adapters.files import FileKeyProvider
from core import conf

log = logging.getLogger(__name__)


class InvalidAIResponse(Exception):
    pass


class AIAnalysisSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")
    batch_index: int = Field(description="Номер заказа из поля ID во входной пачке.")
    priority_value: int = Field(description="Итоговый приоритет заказа: 0 — HIDDEN, 1 — LOW, 2 — MEDIUM, 3 — HIGH.")
    explanation: str = Field(description=SCHEMA_EXPLANATION)
    confidence: float = Field(description=SCHEMA_CONFIDENCE)


class AIAnalyzer:
    _scraper = Scraper(
        retry_on=(InvalidAIResponse, RateLimitError),
        #decrease_on=RateLimitError,
        max_retries=None
    )

    def __init__(self, ai_provider):
        self.provider = ai_provider

        target_technologies = ", ".join(TARGET_TECHNOLOGIES)

        self.system_instruction = textwrap.dedent(
            SYSTEM_INSTRUCTION.format(
                target_technologies=target_technologies
            )
        ).strip()

        self.limit = None

    @staticmethod
    def _build_batch_text(chunk: list[tuple[str, str]]) -> str:
        batch_text_parts = []

        for index, (title, description) in enumerate(chunk):
            batch_text_parts.append(
                f"ID: {index}\n"
                f"Заголовок: {title}\n"
                f"Описание: {description}"
            )

        return "\n---\n".join(batch_text_parts)


    async def _process_single_chunk(
        self,
        chunk: list[tuple[str, str]],
        start_index: int,
    ) -> list[tuple[int, AIAnalysis]]:

        batch_text = self._build_batch_text(chunk)
        ai_results = await self.provider.analyze(
            system_instruction=self.system_instruction,
            batch_text=batch_text,
        )

        parsed_results = []
        for ai_data in ai_results:
            if not 0 <= ai_data.batch_index < len(chunk):
                raise InvalidAIResponse(
                    f"Несуществующий batch_index: "
                    f"{ai_data.batch_index}"
                )

            priority_value = max(
                JobPriority.HIDDEN,
                min(
                    ai_data.priority_value,
                    JobPriority.HIGH,
                ),
            )

            analysis_obj = AIAnalysis(
                priority=JobPriority(priority_value),
                explanation=ai_data.explanation,
                confidence=ai_data.confidence,
            )

            absolute_index = start_index + ai_data.batch_index
            parsed_results.append((absolute_index, analysis_obj))

        return parsed_results

    async def analyze_jobs(
        self,
        jobs_to_analyze: list[tuple[str, str]],
        batch_size: int = 5,
    ) -> list[AIAnalysis | None]:
        if not jobs_to_analyze:
            return []

        result: list[AIAnalysis | None] = [None] * len(jobs_to_analyze)
        factories = []

        for chunk_number, start_index in enumerate(range(0, len(jobs_to_analyze), batch_size)):
            if self.limit is not None and chunk_number >= self.limit:
                break

            chunk = jobs_to_analyze[start_index:start_index + batch_size]

            factories.append(
                Factory(
                    self._process_single_chunk,
                    chunk,
                    start_index,
                    context=start_index
                )
            )
        results, failed = await self._scraper.execute_batch(factories=factories, batch_size=3)

        for _, chunk_result in results:
            for absolute_index, analysis_obj in chunk_result:
                result[absolute_index] = analysis_obj

        for start_index, exc in failed:
            log.error(
                "Не удалось обработать пачку с start_index=%s: %s",
                start_index,
                exc,
            )

        return result



class GeminiProvider:
    def __init__(self):
        self._pool = asyncio.Queue()
        self.key_manager = FileKeyProvider()
        self._background_tasks = set()
        if not self.key_manager.keys:
            raise RuntimeError("Не найдено ни одного API-ключа")

        for key in self.key_manager.keys:
            self._pool.put_nowait(genai.Client(api_key=key))


    async def _cooldown_client(self, client):
        await asyncio.sleep(60)
        self._pool.put_nowait(client)
        log.debug("Ключ вернулся в пул.")


    def cooldown(self, client):
        task = asyncio.create_task(self._cooldown_client(client))
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)


    async def analyze(self, system_instruction: str, batch_text: str) -> list[AIAnalysisSchema]:
        client = await self._pool.get()
        try:
            response = await client.aio.models.generate_content(
                model="gemini-3.6-flash",
                contents=(
                    "Проанализируй следующие заказы "
                    "и верни массив JSON:\n"
                    f"{batch_text}"
                ),
                config={
                    "system_instruction": system_instruction,
                    "response_mime_type": "application/json",
                    "response_schema": list[AIAnalysisSchema],
                },
            )

            parsed_response: list[AIAnalysisSchema] = response.parsed

            if not parsed_response:
                raise InvalidAIResponse(
                    "Gemini вернул пустой ответ или сработал фильтр."
                )

        except ClientError as exc:
            if exc.code == 429:
                self.cooldown(client)
                raise RateLimitError(str(exc)) from exc

            self._pool.put_nowait(client)
            raise

        except Exception as exc:
            log.error("%s", exc)
            self.cooldown(client)
            raise

        self._pool.put_nowait(client)
        return parsed_response


class GroqAnalysisResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    results: list[AIAnalysisSchema]


class GroqProvider:
    def __init__(self):
        self.client = AsyncGroq(api_key=conf.groq_key, max_retries=0)
        self._available = asyncio.Event()
        self._available.set()
        self.next_task = None

    async def _restore(self, delay: float):
        await asyncio.sleep(delay)
        self._available.set()

    async def analyze(
        self,
        system_instruction: str,
        batch_text: str,
    ) -> list[AIAnalysisSchema]:
        try:
            await self._available.wait()
            response = await self.client.chat.completions.create(
                model="openai/gpt-oss-120b",
                messages=[
                    {
                        "role": "system",
                        "content": system_instruction,
                    },
                    {
                        "role": "user",
                        "content": (
                            "Проанализируй следующие заказы "
                            "и верни массив JSON:\n"
                            f"{batch_text}"
                        ),
                    },
                ],
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": "job_analysis",
                        "strict": True,
                        "schema": GroqAnalysisResponse.model_json_schema(),
                    },
                },
            )
            content = response.choices[0].message.content

            if not content:
                raise InvalidAIResponse(
                    "Groq вернул пустой ответ."
                )

        except GroqRateLimitError as exc:
            self._available.clear()
            retry_after = float(exc.response.headers.get("retry-after", 60))
            log.debug("Retry After: %s", retry_after)
            asyncio.create_task(self._restore(retry_after))
            raise RateLimitError(str(exc)) from exc

        parsed = GroqAnalysisResponse.model_validate_json(content)

        return parsed.results