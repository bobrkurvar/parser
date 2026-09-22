from pydantic import ConfigDict, Field, BaseModel
from fl.literals import SCHEMA_EXPLANATION, SCHEMA_CONFIDENCE

class InvalidAIResponse(Exception):
    pass

class AIAnalysisSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")
    batch_index: int = Field(description="Номер заказа из поля ID во входной пачке.")
    priority_value: int = Field(description="Итоговый приоритет заказа: 0 — HIDDEN, 1 — LOW, 2 — MEDIUM, 3 — HIGH.")
    explanation: str = Field(description=SCHEMA_EXPLANATION)
    confidence: float = Field(description=SCHEMA_CONFIDENCE)