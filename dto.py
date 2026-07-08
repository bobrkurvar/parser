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
    explanation: str
    confidence: float
    priority: JobPriority | None = None
    job_id: int | None = None


@dataclass
class JobView:
    job: FreelanceJob
    id: int | None = None
    page_data: "ProjectData | None" = None
    ai: AIAnalysis | None = None
    priority: JobPriority = ai.priority
    is_hidden: bool = False

    def refresh_priority(self, priority: JobPriority):
        self.priority = priority




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