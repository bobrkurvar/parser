import asyncio
import logging

from google import genai
from google.genai.errors import ClientError

from adapters.files import FileKeyProvider
from exceptions import RateLimitError
from scraper_engine import Factory, Scraper

from .schemas import InvalidAIResponse


log = logging.getLogger(__name__)


class GeminiProvider:
    def __init__(self, max_retries: int | None = 3):
        self._pool = asyncio.Queue()
        self.key_manager = FileKeyProvider()
        self._background_tasks = set()
        self._scraper = Scraper(
            retry_on=(RateLimitError,),
            max_retries=max_retries,
        )

        if not self.key_manager.keys:
            raise RuntimeError("Не найдено ни одного API-ключа")

        for key in self.key_manager.keys:
            self._pool.put_nowait(genai.Client(api_key=key))

    async def _cooldown_client(self, client) -> None:
        await asyncio.sleep(60)
        self._pool.put_nowait(client)
        log.debug("Ключ вернулся в пул.")

    def cooldown(self, client) -> None:
        task = asyncio.create_task(self._cooldown_client(client))
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)

    async def _analyze_one(
        self,
        system_instruction: str,
        content: str,
        response_schema: dict,
        index: int,
    ) -> dict:
        log.debug("AI-запрос %s отправлен", index)

        client = await self._pool.get()
        return_to_pool = True

        try:
            response = await client.aio.models.generate_content(
                model="gemini-3.6-flash",
                contents=content,
                config={
                    "system_instruction": system_instruction,
                    "response_mime_type": "application/json",
                    "response_json_schema": response_schema,
                },
            )

            parsed_response = response.parsed
            log.debug("Ответ %s: %s", index, parsed_response)

            if parsed_response is None:
                raise InvalidAIResponse(
                    "Gemini вернул пустой ответ или сработал фильтр."
                )

            return parsed_response

        except ClientError as exc:
            if exc.code == 429:
                return_to_pool = False
                self.cooldown(client)
                raise RateLimitError(str(exc)) from exc
            raise

        finally:
            if return_to_pool:
                self._pool.put_nowait(client)


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
            static=True,
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