from filters import analyze_basic
from dto import JobStaticData, JobPageData, JobPriority, ActiveJob
import logging
from rss_categories import ALL_CATEGORIES
from exceptions import NotFoundError
from infra.infra_html import parse_fl_job_page, offer_range
from infra.infra_xml import parse_fl_rss
from scraper_engine import get_pages, get_offer_data


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
    seen_external_ids, pending_analyze_data, pending_analyze_jobs, jobs_to_save, page_cache = set(), [], [], [], {}
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
    results, _ = await get_pages(client=http_client, jobs=jobs_to_fetch)
    for job, html in results:
        page_data = parse_fl_job_page(html)
        page_cache[job.external_id] = page_data
        if not page_data.is_closed and analyze_basic(title=job.title, description=page_data.description):
            pending_analyze_data.append((job.title, page_data.description))
            pending_analyze_jobs.append(job)
        else:
            jobs_to_save.append(JobStaticData(feed_job=job, priority=JobPriority.HIDDEN, page_data=page_data))

    analyses = await llm.analyze_jobs(pending_analyze_data)

    for job, analysis in zip(pending_analyze_jobs, analyses):
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
) -> list[ActiveJob]:
    # Запросы для получения offer тоже нужно через конкурентные запросы
    page_cache = page_cache or {}
    async with uow:
        active_jobs: tuple[JobStaticData] = await uow.db.read(JobStaticData, loaded="ai_analysis", is_hidden=False)
    valid_jobs: list[ActiveJob] = []
    jobs_to_offer_range: list[JobStaticData] = []
    jobs_to_fetch_page: list[JobStaticData] = []
    hide_jobs_ids = []

    for active_job in active_jobs:
        external_id = active_job.feed_job.external_id
        page_data = page_cache.get(external_id)
        if page_data is None:
            jobs_to_fetch_page.append(active_job)
        elif not page_data.is_closed:
            active_job.page_data = page_data
            jobs_to_offer_range.append(active_job)
        else:
            hide_jobs_ids.append(active_job.id)

    page_results, failed = await get_pages(client=http_client, jobs=jobs_to_fetch_page)
    hide_jobs_ids.extend(job.id for job in failed)
    for job, html in page_results:
        page_data = parse_fl_job_page(html)
        if not page_data.is_closed:
            job.page_data = page_data
            jobs_to_offer_range.append(job)
        else:
            hide_jobs_ids.append(job.id)

    offer_results, failed = await get_offer_data(client=http_client, jobs=jobs_to_offer_range)
    hide_jobs_ids.extend(job.id for job in failed)
    for job, offer_data in offer_results:
        valid_jobs.append(ActiveJob(static_data=job, dynamic_data=offer_range(offer_data)))


    if hide_jobs_ids:
        async with uow:
            await uow.db.update(JobStaticData, {"id": hide_jobs_ids}, is_closed=True, is_hidden=True)

    valid_jobs.sort(
        key=lambda job: job.static_data.priority,
        reverse=True,
    )

    return valid_jobs


async def load_jobs(http_client, llm, uow) -> list[ActiveJob]:
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

