from .yandex import YandexAIProvider
from .groq import GroqProvider

from exceptions import RateLimitError
import logging
from scraper_engine import Scraper, Factory
from abc import ABC, abstractmethod
from typing import Any
from pydantic import BaseModel


log = logging.getLogger(__name__)


class InvalidAIResponse(Exception):
    pass



class BaseAIAnalyzer(ABC):
    _scraper = Scraper(
        retry_on=(RateLimitError, ),
        max_retries=None
    )

    def __init__(self, ai_provider, response_model: type[BaseModel], system_instruction: str, limit: int | None = None):
        self.provider = ai_provider
        self.response_model = response_model
        self.system_instruction = system_instruction

        self.limit = limit

    @staticmethod
    @abstractmethod
    def _build_request(chunk) -> str:
        pass


    @abstractmethod
    def _build_result(self, ai_data):
        pass

    async def _process_single(self, item):
        content = self._build_request(item)

        raw_response = await self.provider.analyze(
            system_instruction=self.system_instruction,
            content=content,
            response_schema=self.response_model.model_json_schema(),
        )

        response = self.response_model.model_validate(raw_response)
        return self._build_result(response)


    async def analyze(self, items: list) -> list:
        if not items:
            return []

        result = [None] * len(items)

        factories = [
            Factory(
                self._process_single,
                item,
                context=index,
            )
            for index, item in enumerate(items)
        ]

        results, failed = await self._scraper.execute_batch(
            factories=factories,
            batch_size=3,
        )

        for index, analysis in results:
            result[index] = analysis

        for index, exc in failed:
            log.error(
                "Не удалось проанализировать элемент %s: %s",
                index,
                exc,
            )

        return result


    # async def _process_single_chunk(
    #     self,
    #     chunk: list[tuple[str, str]],
    #     start_index: int,
    # ) -> list[tuple[int, Any]]:
    #     # анализ выходных данные из провайдера, должен быть batch index
    #     batch_text = self._build_batch_text(chunk)
    #     raw_response: list[dict] = await self.provider.analyze(
    #         system_instruction=self.system_instruction,
    #         content=batch_text,
    #         response_schema=self.response_model.model_json_schema()
    #     )
    #     # if not all("batch_index" in res for res in ai_results):
    #     #     raise ValueError("В ответе нет индекса пачки")
    #     response = self.response_model.model_validate(raw_response)
    #
    #     parsed_results = []
    #     for ai_data in response.results:
    #         if not 0 <= ai_data.batch_index < len(chunk):
    #             raise InvalidAIResponse(
    #                 f"Несуществующий batch_index: "
    #                 f"{ai_data.batch_index}"
    #             )
    #
    #         analysis_obj = self._build_result(ai_data)
    #
    #         absolute_index = start_index + ai_data.batch_index
    #         parsed_results.append((absolute_index, analysis_obj))
    #
    #     return parsed_results


    # async def analyze_batch(
    #     self,
    #     jobs_to_analyze: list[tuple[str, str]],
    #     batch_size: int = 15,
    # ) -> list:
    #     if not jobs_to_analyze:
    #         return []
    #
    #     result = [None] * len(jobs_to_analyze)
    #     factories = []
    #
    #     for chunk_number, start_index in enumerate(range(0, len(jobs_to_analyze), batch_size)):
    #         if self.limit is not None and chunk_number >= self.limit:
    #             break
    #
    #         chunk = jobs_to_analyze[start_index:start_index + batch_size]
    #
    #         factories.append(
    #             Factory(
    #                 self._process_single_chunk,
    #                 chunk,
    #                 start_index,
    #                 context=start_index
    #             )
    #         )
    #     results, failed = await self._scraper.execute_batch(factories=factories, batch_size=3)
    #
    #     for _, chunk_result in results:
    #         for absolute_index, analysis_obj in chunk_result:
    #             result[absolute_index] = analysis_obj
    #
    #     for start_index, exc in failed:
    #         log.error(
    #             "Не удалось обработать пачку с start_index=%s: %s",
    #             start_index,
    #             exc,
    #         )
    #
    #     return result