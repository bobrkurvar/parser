from sqlalchemy import Text, ForeignKey
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from datetime import datetime


class Base(AsyncAttrs, DeclarativeBase):
    pass


class JobView(Base):
    __tablename__ = "job_data"
    id: Mapped[int] = mapped_column(primary_key=True)
    external_id: Mapped[str] = mapped_column(unique=True, index=True)
    human_priority: Mapped[int | None] = mapped_column(default=None)

    # Входные данные (фичи)
    title: Mapped[str] = mapped_column(Text)
    description: Mapped[str] = mapped_column(Text)
    tags_raw: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str] = mapped_column()

    # Ответы "Учителя" (Gemini) - это наши метки для обучения
    ai_priority: Mapped[int] = mapped_column(index=True)
    ai_tech_tags: Mapped[str | None] = mapped_column(Text)
    ai_explanation: Mapped[str | None] = mapped_column(Text)
    ai_confidence: Mapped[float] = mapped_column()

    is_closed: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(default=datetime.now())


class ActiveJobs(Base):
    __tablename__ = "active_jobs"
    job_id: Mapped[int] = mapped_column(ForeignKey("training_dataset.id"), primary_key=True)
    url: Mapped[str]
