from fl.dto import AIAnalysis
from fl.literals import SYSTEM_INSTRUCTION, TARGET_TECHNOLOGIES, SCHEMA_CONFIDENCE, SCHEMA_EXPLANATION
import textwrap
from adapters.llm import BaseAIAnalyzer
from pydantic import BaseModel, ConfigDict, Field
import logging


log = logging.getLogger(__name__)


class AIAnalysisSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")
    matches_profile: bool = Field(
        description=(
            "True — заказ подходит Python backend-разработчику, "
            "False — заказ не подходит."
        )
    )
    explanation: str = Field(description=SCHEMA_EXPLANATION)
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description=SCHEMA_CONFIDENCE,
    )


class AIAnalyzer(BaseAIAnalyzer):
    def __init__(self, ai_provider):
        target_technologies = ", ".join(TARGET_TECHNOLOGIES)
        system_instruction = textwrap.dedent(
            SYSTEM_INSTRUCTION.format(
                target_technologies=target_technologies
            )
        ).strip()

        super().__init__(
            ai_provider=ai_provider,
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


    def _build_result(self, ai_data: AIAnalysisSchema) -> AIAnalysis:
        return AIAnalysis(
            matches_profile=ai_data.matches_profile,
            explanation=ai_data.explanation,
            confidence=ai_data.confidence,
        )
