from filters import analyze_basic
from dto import JobStaticData, JobPageData, JobPriority
import logging
from rss_categories import ALL_CATEGORIES
from exceptions import NotFoundError
from infra.infra_html import parse_fl_job_page, offer_range
from infra.infra_xml import parse_fl_rss
from scraper_engine import get_pages


log = logging.getLogger(__name__)


def get_category_with_subcategory(category_group: dict[str, int]):
    category_id = category_group["category"]
    for name, subcategory in category_group.items():
        if name == "category":
            continue
        yield category_id, name, subcategory


async def fetch_jobs(http_client):
    for cat in ALL_CATEGORIES:
        for category_id, category, subcategory_id in get_category_with_subcategory(cat):
            raw_jobs = await http_client.fetch_rss(category_id=category_id, subcategory_id=subcategory_id)
            jobs = parse_fl_rss(raw_jobs, feed_name=category)
            for job in jobs:
                yield category, job


async def collect_pipeline(http_client, llm, uow) -> dict[int, JobPageData]:
    seen_external_ids, pending_analyze, jobs_to_save, page_cache = set(), [], [], {}
    jobs_to_fetch = []
    async with uow:
        async for feed_name, job in fetch_jobs(http_client):
            if job.external_id in seen_external_ids:
                continue
            seen_external_ids.add(job.external_id)
            try:
                async with uow.savepoint():
                    await uow.db.read_one(JobStaticData, external_id=job.external_id, with_raise=True)
            except NotFoundError:
                jobs_to_fetch.append(job)
    results = await get_pages(client=http_client, jobs=jobs_to_fetch)
    for job, html in results:
        page_data = parse_fl_job_page(html)
        page_cache[job.external_id] = page_data
        if not page_data.is_closed and analyze_basic(title=job.title, description=page_data.description):
            pending_analyze.append((job.title, page_data.description))
        else:
            jobs_to_save.append(JobStaticData(feed_job=job, priority=JobPriority.HIDDEN, page_data=page_data))

    analyses = await llm.analyze_jobs(pending_analyze)

    for job, analysis in zip(pending_analyze, analyses):
        if analysis is None:
            log.error("Нет анализа для данной работы: %s", job)
            continue
        jobs_to_save.append(
            JobStaticData(
                feed_job=job,
                priority=analysis.priority,
                ai=analysis,
                page_data=page_cache[job.external_id]
            )
        )

    if jobs_to_save:
        async with uow:
            await uow.db.create(seq_data=jobs_to_save)

    return page_cache


async def read_active_jobs(
    http_client,
    uow,
    page_cache: dict[int, JobPageData] | None = None,
) -> list[JobStaticData]:
    page_cache = page_cache or {}
    async with uow:
        active_jobs = await uow.db.read(JobStaticData, is_hidden=False)
    valid_jobs: list[JobStaticData] = []
    hide_jobs_ids = []

    for job_view in active_jobs:
        external_id = job_view.job.external_id
        page_data = page_cache.get(external_id)
        if page_data is None:
            html_page = await http_client.fetch_project_page(job_view.job.url)
            page_data = parse_fl_job_page(html_page)

        if not page_data.is_closed:
            fetch_data = await http_client.fetch_offer_range(project_id=external_id)
            offer_data = offer_range(fetch_data)
            log.debug("offer range data: %s page data: %s", offer_data, page_data)
            job_view.page_data, job_view.offer_range = page_data, offer_data
            valid_jobs.append(job_view)
        else:
            hide_jobs_ids.append(job_view.id)

    if hide_jobs_ids:
        async with uow:
            await uow.db.update(JobStaticData, {"id": hide_jobs_ids}, is_hidden=True, is_closed=True)

    valid_jobs.sort(
        key=lambda jv: jv.priority,
        reverse=True,
    )

    return valid_jobs


async def load_jobs(http_client, llm, uow) -> list[JobStaticData]:
    page_cache = await collect_pipeline(
        http_client=http_client,
        llm=llm,
        uow=uow,
    )

    return await read_active_jobs(
        http_client=http_client,
        uow=uow,
        page_cache=page_cache
    )

