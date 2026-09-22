from openai import AsyncOpenAI, RateLimitError as OpenAIRateLimitError
from exceptions import RateLimitError
from core import conf
from .schemas import AIAnalysisSchema, InvalidAIResponse
from pydantic import BaseModel, ConfigDict

class YandexAnalysisResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    results: list[AIAnalysisSchema]


class YandexAIProvider:
    def __init__(self):
        self.client = AsyncOpenAI(
            api_key=conf.yandex_api_key,
            base_url="https://ai.api.cloud.yandex.net/v1",
            project=conf.yandex_folder_id,
            max_retries=0,
        )
        self.analysis_model = self._model_uri("yandexgpt-5-lite/latest")
        self.agent_model = self._model_uri("deepseek-v4-flash/latest")

    @staticmethod
    def _model_uri(model: str) -> str:
        return f"gpt://{conf.yandex_folder_id}/{model}"


    async def analyze(
        self,
        system_instruction: str,
        batch_text: str,
    ) -> list[AIAnalysisSchema]:
        try:
            response = await self.client.chat.completions.create(
                model=self.analysis_model,
                messages=[
                    {
                        "role": "system",
                        "content": system_instruction,
                    },
                    {
                        "role": "user",
                        "content": (
                            "Проанализируй следующие заказы:\n"
                            f"{batch_text}"
                        ),
                    },
                ],
                temperature=0.1,
                max_tokens=1500,
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": "job_analysis",
                        "schema": (
                            YandexAnalysisResponse.model_json_schema()
                        ),
                    },
                },
            )
        except OpenAIRateLimitError as exc:
            raise RateLimitError(str(exc)) from exc

        content = response.choices[0].message.content

        if not content:
            raise InvalidAIResponse("Yandex вернул пустой ответ")

        parsed = YandexAnalysisResponse.model_validate_json(content)

        return parsed.results