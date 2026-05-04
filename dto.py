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

@dataclass
class JobView:
    job: FreelanceJob
    feed_name: str
    basic: BasicAnalysis
    ai: AIAnalysis | None = None

    @property
    def final_priority(self) -> JobPriority:
        if self.ai:
            return self.ai.priority
        return self.basic.priority



@dataclass
class CollectResult:
    all_cnt: int
    passed_cnt: int
    content_filter_cnt: int
    exclude_stack_filter_cnt: int
    jobs: list[JobView]


