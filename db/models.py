from sqlalchemy import  Text
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from datetime import datetime


class Base(AsyncAttrs, DeclarativeBase):
    pass


class TrainingDataset(Base):
    __tablename__ = "training_dataset"
    id: Mapped[int] = mapped_column(primary_key=True)
    # Уникальный ID с биржи (первичный ключ)
    external_id: Mapped[str] = mapped_column(unique=True, index=True)
    human_priority: Mapped[int | None] = mapped_column(default=None)

    # Входные данные (фичи)
    title: Mapped[str] = mapped_column(Text)
    description: Mapped[str] = mapped_column(Text)
    tags_raw: Mapped[str | None] = mapped_column(Text)  # Тэги биржи через запятую
    source: Mapped[str] = mapped_column()  # Название биржи

    # Ответы "Учителя" (Gemini) - это наши метки для обучения
    ai_priority: Mapped[int] = mapped_column(index=True)
    ai_tech_tags: Mapped[str | None] = mapped_column(Text)
    ai_explanation: Mapped[str | None] = mapped_column(Text)
    ai_confidence: Mapped[float] = mapped_column()

    # Техническое поле
    created_at: Mapped[datetime] = mapped_column(default=datetime.now())

    def model_dump(self) -> dict:
        return {
            "id": self.id,
            "external_id": self.external_id,
            "title": self.title,
            "description": self.description,
            "tags_raw": self.tags_raw,
            "source": self.source,
            "ai_priority": self.ai_priority,
            "ai_tech_tags": self.ai_tech_tags,
            "ai_explanation": self.ai_explanation,
            "ai_confidence": self.ai_confidence,
            "human_priority": self.human_priority,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }
