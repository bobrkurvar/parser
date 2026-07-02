from filters import analyze_basic
from dto import JobView, JobPriority, FreelanceJob, ActiveJob
import logging
from rss_categories import MAIN_URL, ALL_CATEGORIES
from exceptions import AlreadyExistsError, NotFoundError
from infra_html import parse_fl_job_page
from infra_xml import parse_fl_rss

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
            raw_jobs = await http_client.fetch(url)
            jobs = parse_fl_rss(raw_jobs)
            for job in jobs:
                yield feed_name, job


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
    async for feed_name, job in fetch_jobs(http_client):
        if job.external_id in seen_external_ids:
            continue
        seen_external_ids.add(job.external_id)
        try:
            await db_manager.read_one(JobView, external_id=job.external_id, with_raise=True)
        except NotFoundError:
            html_page = await http_client.fetch(job.url)
            page_data = parse_fl_job_page(html_page)
            job.description = page_data.description

            if job_view := add_basic_analysis(job=job, feed_name=feed_name):
                job_view.page_data = page_data
                pending_analyze.append(job_view)

    await llm.analyze_batch(pending_analyze)
    await save_analyzed_jobs(db_manager=db_manager, jobs=pending_analyze)


async def read_active_jobs(http_client, db_manager):
    active_jobs = await db_manager.read(ActiveJob, loaded="data")
    approve_jobs = []
    for job in active_jobs:
        html_page = await http_client.fetch(job.url)
        page_data = parse_fl_job_page(html_page)
        if page_data.is_closed:
            await db_manager.delete(ActiveJob, id=job.id)
        else:
            approve_jobs.append(job)
    return approve_jobs
