from filters import analyze_basic
from dto import CollectResult, JobView, JobPriority, FreelanceJob
import logging
from rss_categories import MAIN_URL, ALL_CATEGORIES
from exceptions import AlreadyExistsError, NotFoundError
from dataclasses import dataclass, field

log = logging.getLogger(__name__)


def build_urls(category_group: dict[str, int]) -> list[tuple[str, str]]:
    category, urls = category_group["category"], []
    for name, subcategory in category_group.items():
        if name == "category":
            continue

        url = f"{MAIN_URL}?category={category}&subcategory={subcategory}"
        urls.append((name, url))

    return urls


async def fetch_jobs(http_client):
    for cat in ALL_CATEGORIES:
        urls = build_urls(cat)
        for feed_name, url in urls:
            for job in await http_client.fetch_fl_jobs(url):
                yield feed_name, job


# @dataclass(slots=True)
# class BasicCollectState:
#     visible_jobs: list[JobView] = field(default_factory=list)
#     pending_ai: list[JobView] = field(default_factory=list)
#
#     all_cnt: int = 0
#     content_filter_cnt: int = 0
#     exclude_stack_filter_cnt: int = 0


# async def collect_with_basic_analysis(http_client, db_manager) -> BasicCollectState:
#     state = BasicCollectState()
#     seen_external_ids = set()
#
#     async for feed_name, job in fetch_jobs(http_client):
#         if job.external_id in seen_external_ids:
#             continue
#         seen_external_ids.add(job.external_id)
#         state.all_cnt += 1
#         # basic_analysis = analyze_basic(job)
#         # if basic_analysis.excluded_stack:
#         #     state.exclude_stack_filter_cnt += 1
#         #
#         # if not basic_analysis.content_keywords:
#         #     state.content_filter_cnt += 1
#         #
#         # if basic_analysis.priority <= JobPriority.HIDDEN:
#         #     continue
#         try:
#             job_view = await db_manager.read_one(JobView, external_id=job.external_id, with_raise=True)
#             if not job_view.is_hidden():
#                 state.visible_jobs.append(job_view)
#         except NotFoundError:
#             basic_analysis = analyze_basic(job)
#             if basic_analysis.excluded_stack:
#                 state.exclude_stack_filter_cnt += 1
#
#             if not basic_analysis.content_keywords:
#                 state.content_filter_cnt += 1
#
#             if basic_analysis.priority <= JobPriority.HIDDEN:
#                 continue
#             state.pending_ai.append(
#                 JobView(
#                     job=job,
#                     basic=basic_analysis,
#                     feed_name=feed_name,
#                 )
#             )
#     return state


# @dataclass(slots=True)
# class BasicCollectState:
#     pending_ai: list[JobView] = field(default_factory=list)
#     all_cnt: int = 0
#     content_filter_cnt: int = 0
#     exclude_stack_filter_cnt: int = 0


def add_basic_analysis(
    job: FreelanceJob,
    feed_name: str,
) -> JobView | None:
    basic_analysis = analyze_basic(job)

    if basic_analysis.priority <= JobPriority.HIDDEN:
        return None

    return JobView(
        job=job,
        basic=basic_analysis,
        feed_name=feed_name,
    )



async def save_analyzed_jobs(db_manager, jobs: list[JobView]):
    for jv in jobs:
        if jv.ai is None:
            continue
        try:
            await db_manager.create(jv)
        except AlreadyExistsError:
            pass


async def collect_pipeline(http_client, llm, db_manager):
    seen_external_ids, pending_analyze = set(), []
    async for feed_name, jobs in fetch_jobs(http_client):
        for job in jobs:
            if job.external_id in seen_external_ids:
                continue
            seen_external_ids.add(job.external_id)
            try:
                await db_manager.read_one(JobView, external_id=job.external_id, with_raise=True)
            except NotFoundError:
                #await parse()
                if job_view := add_basic_analysis(job=job, feed_name=feed_name):
                    pending_analyze.append(job_view)

    await llm.analyze_batch(pending_analyze)
    await save_analyzed_jobs(db_manager=db_manager, jobs=pending_analyze)

