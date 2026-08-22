from google.genai.errors import ClientError
from google import genai
from pydantic import BaseModel, Field
from dto import AIAnalysis, JobPriority
from exceptions import RateLimitError
from literals import SYSTEM_INSTRUCTION, SCHEMA_EXPLANATION, SCHEMA_CONFIDENCE, TARGET_TECHNOLOGIES
import asyncio
import logging
from .files import KeyProvider
import textwrap
from scraper_engine import Scraper, Factory

log = logging.getLogger(__name__)


class InvalidGeminiResponse(Exception):
    pass


class GeminiSchema(BaseModel):
    batch_index: int = Field(description="Номер заказа из поля ID во входной пачке.")
    priority_value: int = Field(description="Итоговый приоритет заказа: 0 — HIDDEN, 1 — LOW, 2 — MEDIUM, 3 — HIGH.")
    explanation: str = Field(description=SCHEMA_EXPLANATION)
    confidence: float = Field(description=SCHEMA_CONFIDENCE)


class GeminiAnalyzer:
    _scraper = Scraper(retry_on=(InvalidGeminiResponse, RateLimitError), decrease_on=RateLimitError)

    def __init__(self):
        self._pool = asyncio.Queue()
        self.key_manager = KeyProvider()
        self._background_tasks = set()
        if not self.key_manager.keys:
            raise RuntimeError("Не найдено ни одного API-ключа Gemini")

        for key in self.key_manager.keys:
            self._pool.put_nowait(genai.Client(api_key=key))
        target_technologies = ", ".join(TARGET_TECHNOLOGIES)

        self.system_instruction = textwrap.dedent(SYSTEM_INSTRUCTION.format(target_technologies=target_technologies)).strip()
        self.limit = None

    def _build_batch_text(self, chunk: list[tuple[str, str]]) -> str:
        batch_text_parts: list[str] = []

        for index, (title, description) in enumerate(chunk):
            batch_text_parts.append(
                f"ID: {index}\n"
                f"Заголовок: {title}\n"
                f"Описание: {description}"
            )

        return "\n---\n".join(batch_text_parts)

    async def _cooldown_client(self, client: genai.Client):
        #log.warning("Ключ поймал ошибку (вероятно 429). Уходит на паузу 60 сек...")
        await asyncio.sleep(60)
        self._pool.put_nowait(client)
        log.debug("Ключ вернулся в пул.")


    async def _process_single_chunk(self, chunk: list[tuple[str, str]], start_index: int) -> list[tuple[int, AIAnalysis]]:
        """Изолированная задача для обработки одной пачки данных."""
        batch_text = self._build_batch_text(chunk)

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
                    "system_instruction": self.system_instruction,
                    "response_mime_type": "application/json",
                    "response_schema": list[GeminiSchema],
                },
            )

            if not response.parsed:
                raise InvalidGeminiResponse(
                    "Gemini вернул пустой ответ или сработал фильтр."
                )

            parsed_results = []
            for ai_data in response.parsed:
                if not 0 <= ai_data.batch_index < len(chunk):
                    log.error("Несуществующий batch_index: %s", ai_data.batch_index)
                    raise InvalidGeminiResponse(
                        f"Несуществующий batch_index: {ai_data.batch_index}"
                    )

                priority_value = max(JobPriority.HIDDEN, min(ai_data.priority_value, JobPriority.HIGH))

                analysis_obj = AIAnalysis(
                    priority=JobPriority(priority_value),
                    explanation=ai_data.explanation,
                    confidence=ai_data.confidence,
                )

                absolute_index = start_index + ai_data.batch_index
                parsed_results.append((absolute_index, analysis_obj))

            self._pool.put_nowait(client)
            return parsed_results

        except ClientError as exc:
            task = asyncio.create_task(self._cooldown_client(client))
            self._background_tasks.add(task)
            task.add_done_callback(self._background_tasks.discard)
            if exc.code == 429:
                raise RateLimitError(str(exc)) from exc

            raise

        except Exception as exc:
            log.error("%s", exc)
            task = asyncio.create_task(self._cooldown_client(client))
            self._background_tasks.add(task)
            task.add_done_callback(self._background_tasks.discard)
            raise

    async def analyze_jobs(
        self,
        jobs_to_analyze: list[tuple[str, str]],
        batch_size: int = 15,
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

    # async def _process_single_chunk(self, chunk: list[tuple[str, str]], start_index: int) -> list[tuple[int, AIAnalysis]]:
    #     """Изолированная задача для обработки одной пачки данных."""
    #     batch_text, retries = self._build_batch_text(chunk), 0
    #
    #     while retries < 5:
    #         client = await self._pool.get()
    #         try:
    #             response = await client.aio.models.generate_content(
    #                 model="gemini-3.6-flash",
    #                 contents=(
    #                     "Проанализируй следующие заказы "
    #                     "и верни массив JSON:\n"
    #                     f"{batch_text}"
    #                 ),
    #                 config={
    #                     "system_instruction": self.system_instruction,
    #                     "response_mime_type": "application/json",
    #                     "response_schema": list[GeminiSchema],
    #                 },
    #             )
    #
    #             if not response.parsed:
    #                 raise RuntimeError("Gemini вернул пустой ответ или сработал фильтр.")
    #
    #             parsed_results = []
    #             for ai_data in response.parsed:
    #                 if not 0 <= ai_data.batch_index < len(chunk):
    #                     log.error("Несуществующий batch_index: %s", ai_data.batch_index)
    #                     continue
    #
    #                 priority_value = max(JobPriority.HIDDEN, min(ai_data.priority_value, JobPriority.HIGH))
    #
    #                 analysis_obj = AIAnalysis(
    #                     priority=JobPriority(priority_value),
    #                     explanation=ai_data.explanation,
    #                     confidence=ai_data.confidence,
    #                 )
    #
    #                 absolute_index = start_index + ai_data.batch_index
    #                 parsed_results.append((absolute_index, analysis_obj))
    #
    #             self._pool.put_nowait(client)
    #             return parsed_results
    #
    #         except Exception as exc:
    #             log.error("%s", exc)
    #             retries += 1
    #             task = asyncio.create_task(self._cooldown_client(client))
    #             self._background_tasks.add(task)
    #             task.add_done_callback(self._background_tasks.discard)
    #             await asyncio.sleep(0)
    #
    #     log.error("Пачка вакансий (индекс %s) пропущена после %s неудачных попыток.", start_index, retries)
    #     return []

    # async def analyze_jobs(
    #     self,
    #     jobs_to_analyze: list[tuple[str, str]],
    #     batch_size: int = 15,
    # ) -> list[AIAnalysis | None]:
    #     if not jobs_to_analyze:
    #         return []
    #
    #     result: list[AIAnalysis | None] = [None] * len(jobs_to_analyze)
    #     tasks = []
    #
    #     for chunk_number, start_index in enumerate(range(0, len(jobs_to_analyze), batch_size)):
    #         if self.limit is not None and chunk_number >= self.limit:
    #             break
    #
    #         chunk = jobs_to_analyze[start_index:start_index + batch_size]
    #         tasks.append(self._process_single_chunk(chunk, start_index))
    #
    #     results = await asyncio.gather(*tasks)
    #     for chunk_result in results:
    #         for absolute_index, analysis_obj in chunk_result:
    #             result[absolute_index] = analysis_obj
    #
    #     return result
