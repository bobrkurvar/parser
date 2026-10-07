from .yandex import YandexAIProvider
from .groq import GroqProvider
from .gemini import GeminiProvider

import logging
from abc import ABC, abstractmethod
from pydantic import BaseModel


log = logging.getLogger(__name__)


class InvalidAIResponse(Exception):
    pass



class BaseAIAnalyzer(ABC):

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


    async def analyze(self, items: list) -> list:
        if not items:
            return []

        contents = [
            self._build_request(item)
            for item in items
        ]

        raw_results = await self.provider.analyze_many(
            contents=contents,
            system_instruction=self.system_instruction,
            response_schema=self.response_model.model_json_schema(),
        )

        result = []

        for raw_response in raw_results:
            if raw_response is None:
                result.append(None)
                continue

            response = self.response_model.model_validate(raw_response)
            result.append(self._build_result(response))

        return result



