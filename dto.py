from dataclasses import dataclass
from enum import IntEnum


class JobPriority(IntEnum):
    HIDDEN = 0
    LOW = 1
    MEDIUM = 2
    HIGH = 3


@dataclass
class FreelanceJob:
    feed_name: str
    source: str
    external_id: str
    title: str
    description: str
    url: str
    tags: list[str]
    published_at: str | None = None
    budget_text: str | None = None


# @dataclass
# class BasicAnalysis:
#     priority: JobPriority
#     content_keywords: list[str]
#     excluded_stack: dict[str, list[str]]
#     reason: str


@dataclass
class AIAnalysis:
    priority: JobPriority
    explanation: str
    tech_tags: list[str]
    confidence: float

    # @classmethod
    # def from_db(cls, row: dict):
    #     return cls(
    #         priority=JobPriority(row["ai_priority"]),
    #         explanation=row["ai_explanation"] or "",
    #         confidence=row["ai_confidence"],
    #         tech_tags=row["ai_tech_tags"].split(", ") if row["ai_tech_tags"] else []
    #     )


@dataclass
class JobView:
    #feed_name: str
    job: FreelanceJob
    #basic: BasicAnalysis
    human_priority: JobPriority | None = None
    page_data: "FlJobPage | None" = None
    ai: AIAnalysis | None = None

    @property
    def final_priority(self) -> JobPriority | None:
        if self.human_priority is not None:
            return self.human_priority
        if self.ai:
            return self.ai.priority

    def is_hidden(self):
        return self.final_priority == JobPriority.HIDDEN




@dataclass
class CollectResult:
    all_cnt: int
    passed_cnt: int
    content_filter_cnt: int
    exclude_stack_filter_cnt: int
    jobs: list[JobView]


@dataclass
class ActiveJob:
    id: int
    job_data: JobView | None = None


# Динамические данные, которые я получаю после парса страницы
@dataclass(slots=True)
class FlJobPage:
    responses_count: int | None
    response_price_min: int | None
    response_price_max: int | None
    is_closed: bool = False