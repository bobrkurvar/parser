from sqlalchemy import Text, ForeignKey, DateTime
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from datetime import datetime, timezone


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

    ai_priority: Mapped[int] = mapped_column(index=True)
    #ai_tech_tags: Mapped[str | None] = mapped_column(Text)
    ai_explanation: Mapped[str | None] = mapped_column(Text)
    ai_confidence: Mapped[float] = mapped_column()

    is_closed: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )


class ActiveJob(Base):
    __tablename__ = "active_jobs"

    id: Mapped[int] = mapped_column(
        ForeignKey("job_data.id", ondelete="CASCADE"),
        primary_key=True,
    )

    job_data: Mapped[JobView] = relationship(
        "JobView",
        cascade="save-update",
        lazy="joined", # по умолчанию подгрузит сам
    )