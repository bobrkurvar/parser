from dataclasses import dataclass
from enum import IntEnum


class JobPriority(IntEnum):
    HIDDEN = 0
    LOW = 1
    MEDIUM = 2
    HIGH = 3


@dataclass
class FreelanceJob:
    source: str
    external_id: str
    title: str
    description: str
    url: str
    tags: list[str]
    published_at: str | None = None


@dataclass
class BasicAnalysis:
    priority: JobPriority
    content_keywords: list[str]
    excluded_stack: dict[str, list[str]]
    reason: str

@dataclass
class AIAnalysis:
    priority: JobPriority
    explanation: str
    tech_tags: list[str]
    confidence: float

    @classmethod
    def from_db(cls, row: dict):
        return cls(
            priority=JobPriority(row["ai_priority"]),
            explanation=row["ai_explanation"] or "",
            confidence=row["ai_confidence"],
            tech_tags=row["ai_tech_tags"].split(", ") if row["ai_tech_tags"] else []
        )


@dataclass
class JobView:
    feed_name: str
    job: FreelanceJob
    basic: BasicAnalysis
    ai: AIAnalysis | None = None

    @property
    def final_priority(self) -> JobPriority:
        if self.ai:
            return self.ai.priority
        return self.basic.priority

    def to_db(self) -> dict:
        return {
            "external_id": self.job.external_id,
            "title": self.job.title,
            "description": self.job.description,
            "tags_raw": ", ".join(self.job.tags) if self.job.tags else None,
            "source": self.feed_name,

            # Ответы нейросети (из jv.ai)
            "ai_priority": self.ai.priority.value,
            "ai_tech_tags": ", ".join(self.ai.tech_tags) if self.ai.tech_tags else None,
            "ai_explanation": self.ai.explanation,
            "ai_confidence": self.ai.confidence,
        }



@dataclass
class CollectResult:
    all_cnt: int
    passed_cnt: int
    content_filter_cnt: int
    exclude_stack_filter_cnt: int
    jobs: list[JobView]


