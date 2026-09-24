from exceptions import RateLimitError
import asyncio
import logging
from groq import AsyncGroq
from groq import RateLimitError as GroqRateLimitError
from core import conf
from .schemas import InvalidAIResponse
import json

log = logging.getLogger(__name__)



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
        content: str,
        response_schema: dict,
    ):
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
                        "content": content,
                    },
                ],
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": "job_analysis",
                        "strict": True,
                        "schema": response_schema,
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

        # parsed = GroqAnalysisResponse.model_validate_json(content)
        #
        # return parsed.results
        try:
            return json.loads(content)
        except json.JSONDecodeError as exc:
            raise InvalidAIResponse(
                "Провайдер вернул невалидный JSON"
            ) from exc