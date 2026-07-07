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
    external_id: int
    title: str
    description: str
    url: str
    tags: list[str]
    published_at: str | None = None
    budget_text: str | None = None


@dataclass
class AIAnalysis:
    priority: JobPriority
    explanation: str
    confidence: float


@dataclass
class JobView:
    job: FreelanceJob
    priority: JobPriority
    id: int | None = None
    human_priority: JobPriority | None = None
    page_data: "ProjectData | None" = None
    ai: AIAnalysis | None = None

    @property
    def final_priority(self) -> JobPriority | None:
        if self.human_priority is not None:
            return self.human_priority
        # if self.ai:
        #     return self.ai.priority
        return self.priority


    def is_hidden(self):
        return self.final_priority == JobPriority.HIDDEN


@dataclass
class CollectResult:
    all_cnt: int
    passed_cnt: int
    content_filter_cnt: int
    exclude_stack_filter_cnt: int
    jobs: list[JobView]


@dataclass(slots=True)
class OfferRange:
    responses_count: int | None
    response_price_min: int | None
    response_price_max: int | None


@dataclass
class ProjectPageData:
    budget_text: str | None
    description: str
    is_closed: bool


@dataclass(slots=True)
class ProjectData:
    offer_range: OfferRange
    page_data: ProjectPageData