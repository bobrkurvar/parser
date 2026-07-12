from dataclasses import dataclass
from enum import IntEnum
from datetime import datetime


class JobPriority(IntEnum):
    HIDDEN = 0
    LOW = 1
    MEDIUM = 2
    HIGH = 3


@dataclass
class FeedJob:
    feed_name: str
    source: str
    external_id: int
    title: str
    url: str
    tags: list[str]
    published_at: str | datetime | None = None


@dataclass
class JobPageData:
    is_closed: bool
    budget_text: str | None
    description: str


@dataclass(slots=True)
class OfferRange:
    responses_count: int | None
    response_price_min: int | None
    response_price_max: int | None


@dataclass
class AIAnalysis:
    explanation: str
    confidence: float
    priority: JobPriority
    job_id: int | None = None


@dataclass
class JobStaticData:
    feed_job: FeedJob
    priority: JobPriority
    page_data: JobPageData
    id: int | None = None
    ai: AIAnalysis | None = None

    @property
    def is_hidden(self):
        return self.page_data.is_closed or self.priority == JobPriority.HIDDEN


@dataclass
class ActiveJob:
    static_data: JobStaticData
    dynamic_data: OfferRange



@dataclass
class CollectResult:
    all_cnt: int
    passed_cnt: int
    content_filter_cnt: int
    exclude_stack_filter_cnt: int
    jobs: list[ActiveJob]

