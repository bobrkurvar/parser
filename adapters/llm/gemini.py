from google.genai.errors import ClientError
from google import genai
from exceptions import RateLimitError
import asyncio
import logging
from adapters.files import FileKeyProvider
from .schemas import InvalidAIResponse, AIAnalysisSchema

log = logging.getLogger(__name__)




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
