from sqlalchemy import Text, ForeignKey, DateTime, CheckConstraint
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from datetime import datetime, timezone
from dto import JobPriority


class Base(AsyncAttrs, DeclarativeBase):
    pass


class JobView(Base):
    __tablename__ = "job_data"
    id: Mapped[int] = mapped_column(primary_key=True)
    url: Mapped[str]
    feed_name: Mapped[str]
    external_id: Mapped[int] = mapped_column(unique=True, index=True)
    human_priority: Mapped[int | None] = mapped_column(default=None)

    title: Mapped[str] = mapped_column(Text)
    description: Mapped[str] = mapped_column(Text)
    tags_raw: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str] = mapped_column()
    priority: Mapped[int]
    is_closed: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    __table_args__ = (
        CheckConstraint(
            "status_name IN ({})".format(
                ", ".join(f"'{priority}'" for priority in JobPriority)
            ),
            name="check_priority",
        ),
    )


class AiAnalysis(Base):
    __tablename__ = "ai_analysis"
    job_id: Mapped[int] = mapped_column(
        ForeignKey("job_data.id", ondelete="CASCADE"),
        primary_key=True,
    )
    ai_explanation: Mapped[str | None] = mapped_column(Text)
    ai_confidence: Mapped[float] = mapped_column()


