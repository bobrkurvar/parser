from openai import AsyncOpenAI, RateLimitError as OpenAIRateLimitError
from exceptions import RateLimitError
from core import conf
from .schemas import InvalidAIResponse
import json
from scraper_engine import Scraper, Factory
import logging

log = logging.getLogger(__name__)


class YandexAIProvider:
    def __init__(self, max_retries: int | None = 3):
        self.client = AsyncOpenAI(
            api_key=conf.yandex_api_key,
            base_url="https://ai.api.cloud.yandex.net/v1",
            project=conf.yandex_folder_id,
            max_retries=0,
        )
        self.analysis_model = self._model_uri("yandexgpt-5-lite/latest")
        self.agent_model = self._model_uri("deepseek-v4-flash/latest")
        self._alice_llm = self._model_uri("aliceai-llm-flash/latest")
        self._scraper = Scraper(
            retry_on=(RateLimitError,),
            max_retries=max_retries,
        )

    @staticmethod
    def _model_uri(model: str) -> str:
        return f"gpt://{conf.yandex_folder_id}/{model}"


    async def _analyze_one(
        self,
        system_instruction: str,
        content: str,
        response_schema: dict,
        index: int
    ) -> dict:
        log.debug("AI-запрос %s отправлен", index)
        try:
            response = await self.client.chat.completions.create(
                model=self._alice_llm,
                messages=[
                    {
                        "role": "system",
                        "content": system_instruction,
                    },
                    {
                        "role": "user",
                        "content": content
                    },
                ],
                temperature=0.1,
                max_tokens=1500,
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": "job_analysis",
                        "strict": True,
                        "schema": response_schema
                    },
                },
            )
        except OpenAIRateLimitError as exc:
            raise RateLimitError(str(exc)) from exc

        choice = response.choices[0]
        content = response.choices[0].message.content
        log.debug("Ответ %s", content)

        if not content:
            log.warning(
                "Пустой AI-ответ: finish_reason=%s, message=%s, usage=%s",
                choice.finish_reason,
                choice.message,
                response.usage,
            )

        try:
            return json.loads(content)
        except json.JSONDecodeError as exc:
            raise InvalidAIResponse(
                "Провайдер вернул невалидный JSON"
            ) from exc


    async def analyze_many(
        self,
        contents: list[str],
        system_instruction: str,
        response_schema: dict,
    ) -> list[dict | None]:
        log.debug("Всего запросов: %s", len(contents))
        result = [None] * len(contents)

        factories = [
            Factory(
                self._analyze_one,
                system_instruction=system_instruction,
                content=content,
                response_schema=response_schema,
                index=index,
                context=index,
            )
            for index, content in enumerate(contents)
        ]

        results, failed = await self._scraper.collect_all(
            factories=factories,
            batch_size=10,
            static=True
        )

        for index, raw_response in results:
            result[index] = raw_response

        for index, exc in failed:
            log.error(
                "Не удалось выполнить AI-запрос %s: %s",
                index,
                exc,
            )

        return result