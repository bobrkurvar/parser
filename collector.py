from filters import analyze_basic
from dto import CollectResult, JobView, JobPriority
import logging
from rss_categories import MAIN_URL, ALL_CATEGORIES
from domain.training import TrainingDataset
from domain.exceptions import AlreadyExistsError

log = logging.getLogger(__name__)


def build_urls(category_group: dict[str, int]) -> list[tuple[str, str]]:
    category = category_group["category"]

    urls = []

    for name, subcategory in category_group.items():
        if name == "category":
            continue

        url = f"{MAIN_URL}?category={category}&subcategory={subcategory}"
        urls.append((name, url))

    return urls


async def collect_jobs(jobs, llm) -> CollectResult:
    seen: set[str] = set()
    passed_jobs: list[JobView] = []
    all_cnt = content_filter_cnt = exclude_stack_filter_cnt = 0

    for cat in ALL_CATEGORIES:
        urls = build_urls(cat)
        for feed_name, url in urls:
            jobs = await http_client.fetch_fl_jobs(url)

            for job in jobs:
                all_cnt += 1

                if job.external_id in seen:
                    continue
                seen.add(job.external_id)

                basic = analyze_basic(job)
                if basic.excluded_stack:
                    exclude_stack_filter_cnt += 1

                if not basic.content_keywords:
                    content_filter_cnt += 1

                if basic.priority > JobPriority.HIDDEN:
                    passed_jobs.append(
                        JobView(job=job, basic=basic, feed_name=feed_name)
                    )

    if passed_jobs:
        await llm.analyze_batch(passed_jobs)

    passed_jobs.sort(key=lambda item: item.final_priority, reverse=True)

    return CollectResult(
        all_cnt=all_cnt,
        passed_cnt=len(passed_jobs),
        content_filter_cnt=content_filter_cnt,
        exclude_stack_filter_cnt=exclude_stack_filter_cnt,
        jobs=passed_jobs,
    )

async def save_analysis(result: CollectResult, db_manager):
    for jv in result.jobs:
        if not jv.ai:
            continue

        row = {
            "external_id": jv.job.external_id,
            "title": jv.job.title,
            "description": jv.job.description,
            "tags_raw": ", ".join(jv.job.tags) if jv.job.tags else None,
            "source": jv.feed_name,

            # Ответы нейросети (из jv.ai)
            "ai_priority": jv.ai.priority.value,
            "ai_tech_tags": ", ".join(jv.ai.tech_tags) if jv.ai.tech_tags else None,
            "ai_explanation": jv.ai.explanation,
            "ai_confidence": jv.ai.confidence,

            # Базовая линия (из jv.basic)
            "basic_priority": jv.basic.priority.value
        }
        try:
            await db_manager.create(TrainingDataset, **row)
        except AlreadyExistsError:
            pass


# async def collect_and_save(http_client, llm, db_manager):
#     total_jobs = []
#     for cat in ALL_CATEGORIES:
#         urls = build_urls(cat)
#         for feed_name, url in urls:
#             jobs = await http_client.fetch_fl_jobs(url)
#             in_db = await db_manager.read(TrainingDataset, external_id=[job.external_id for job in jobs])
#
#     result = await collect_jobs(http_client, llm)
#     await save_analysis(result, db_manager)
#     return result

