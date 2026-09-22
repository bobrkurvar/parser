from exceptions import RateLimitError
from fl.literals import  SCHEMA_EXPLANATION, SCHEMA_CONFIDENCE
import asyncio
import logging
from groq import AsyncGroq
from groq import RateLimitError as GroqRateLimitError
from pydantic import BaseModel, Field, ConfigDict
from core import conf
from .schemas import InvalidAIResponse

log = logging.getLogger(__name__)




class AIAnalysisSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")
    batch_index: int = Field(description="Номер заказа из поля ID во входной пачке.")
    priority_value: int = Field(description="Итоговый приоритет заказа: 0 — HIDDEN, 1 — LOW, 2 — MEDIUM, 3 — HIGH.")
    explanation: str = Field(description=SCHEMA_EXPLANATION)
    confidence: float = Field(description=SCHEMA_CONFIDENCE)

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