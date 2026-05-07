from filters import analyze_basic
from dto import CollectResult, JobView, JobPriority, AIAnalysis
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



async def collect_and_save(http_client, llm, db_manager):
    jobs_to_ai_analysis = []
    results = []
    all_cnt = content_filter_cnt = exclude_stack_filter_cnt = 0
    for cat in ALL_CATEGORIES:
        urls = build_urls(cat)
        for feed_name, url in urls:
            jobs = await http_client.fetch_fl_jobs(url)
            for job in jobs:
                all_cnt += 1

                basic_analysis = analyze_basic(job)
                if basic_analysis.excluded_stack:
                    exclude_stack_filter_cnt += 1

                if not basic_analysis.content_keywords:
                    content_filter_cnt += 1

                if basic_analysis.priority > JobPriority.HIDDEN:
                    if row := await db_manager.read(TrainingDataset, external_id=job.external_id):
                        ai_analysis = AIAnalysis.from_db(row[0])
                        if ai_analysis.priority > JobPriority.HIDDEN:
                            results.append(JobView(job=job, basic=basic_analysis, ai=ai_analysis, feed_name=feed_name))
                    else:
                        jobs_to_ai_analysis.append(JobView(job=job, basic=basic_analysis, feed_name=feed_name))

    await llm.analyze_batch(jobs_to_ai_analysis)
    for jv in jobs_to_ai_analysis:
        if not jv.ai:
            continue
        try:
            await db_manager.create(TrainingDataset, **jv.to_db())
        except AlreadyExistsError:
            pass

    results += [job for job in jobs_to_ai_analysis if job.final_priority > JobPriority.HIDDEN]
    results.sort(key=lambda job: job.final_priority, reverse=True)
    result = CollectResult(
        all_cnt=all_cnt,
        passed_cnt=len(results),
        content_filter_cnt=content_filter_cnt,
        exclude_stack_filter_cnt=exclude_stack_filter_cnt,
        jobs=results
    )
    return result

