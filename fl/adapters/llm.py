from fl.dto import AIAnalysis, JobPriority
from fl.literals import SYSTEM_INSTRUCTION, TARGET_TECHNOLOGIES, SCHEMA_CONFIDENCE, SCHEMA_EXPLANATION
import textwrap
from adapters.llm import BaseAIAnalyzer
from pydantic import BaseModel, ConfigDict, Field
import logging
import json


log = logging.getLogger(__name__)


class AIAnalysisSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")
    batch_index: int = Field(description="Номер заказа из поля ID во входной пачке.")
    priority_value: int = Field(description="Итоговый приоритет заказа: 0 — HIDDEN, 1 — LOW, 2 — MEDIUM, 3 — HIGH.")
    explanation: str = Field(description=SCHEMA_EXPLANATION)
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description=SCHEMA_CONFIDENCE,
    )


# class AnalysisResponse(BaseModel):
#     model_config = ConfigDict(extra="forbid")
#     results: list[AIAnalysisSchema]



class AIAnalyzer(BaseAIAnalyzer):
    # _scraper = Scraper(
    #     retry_on=(InvalidAIResponse, RateLimitError),
    #     max_retries=None
    # )

    def __init__(self, ai_provider):
        target_technologies = ", ".join(TARGET_TECHNOLOGIES)
        system_instruction = textwrap.dedent(
            SYSTEM_INSTRUCTION.format(
                target_technologies=target_technologies
            )
        ).strip()

        super().__init__(
            ai_provider=ai_provider,
            #response_schema=AnalysisResponse.model_json_schema(),
            response_model=AIAnalysisSchema,
            system_instruction=system_instruction
        )

    @staticmethod
    def _build_request(
        item: tuple[str, str],
    ) -> str:
        title, description = item

        return (
            f"Заголовок: {title}\n"
            f"Описание: {description}"
        )
    # @staticmethod
    # def _build_batch_text(chunk: list[tuple[str, str]]) -> str:
    #     batch_text_parts = []
    #
    #     for index, (title, description) in enumerate(chunk):
    #         batch_text_parts.append(
    #             f"ID: {index}\n"
    #             f"Заголовок: {title}\n"
    #             f"Описание: {description}"
    #         )
    #
    #     return "\n---\n".join(batch_text_parts)


    def _build_result(self, ai_data: AIAnalysisSchema):
        priority_value = max(
            JobPriority.HIDDEN.value,
            min(
                ai_data.priority_value,
                JobPriority.HIGH.value,
            ),
        )

        return AIAnalysis(
            priority=JobPriority(priority_value),
            explanation=ai_data.explanation,
            confidence=ai_data.confidence,
        )
