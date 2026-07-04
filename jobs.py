from filters import analyze_basic
from dto import JobView, ActiveJob, ProjectData, ProjectPageData
import logging
from rss_categories import ALL_CATEGORIES
from exceptions import AlreadyExistsError, NotFoundError
from infra.infra_html import parse_fl_job_page, offer_range
from infra.infra_xml import parse_fl_rss

log = logging.getLogger(__name__)


# def build_urls(category_group: dict[str, int]) -> list[tuple[str, str]]:
#     category, urls = category_group["category"], []
#     for name, subcategory in category_group.items():
#         if name == "category":
#             continue
#
#         url = f"{MAIN_URL}?category={category}&subcategory={subcategory}"
#         urls.append((name, url))
#
#     return urls

def get_category_with_subcategory(category_group: dict[str, int]):
    category_id = category_group["category"]
    for name, subcategory in category_group.items():
        if name == "category":
            continue
        yield category_id, name, subcategory


# async def fetch_jobs(http_client):
#     for cat in ALL_CATEGORIES:
#         urls = build_urls(cat)
#         for feed_name, url in urls:
#             raw_jobs = await http_client.fetch(url)
#             jobs = parse_fl_rss(raw_jobs, feed_name=feed_name)
#             for job in jobs:
#                 yield feed_name, job

async def fetch_jobs(http_client):
    for cat in ALL_CATEGORIES:
        for category_id, category, subcategory_id in get_category_with_subcategory(cat):
            raw_jobs = await http_client.fetch_rss(category_id=category_id, subcategory_id=subcategory_id)
            jobs = parse_fl_rss(raw_jobs, feed_name=category)
            for job in jobs:
                yield category, job


async def save_analyzed_jobs(uow, jobs: list[JobView]) -> None:
    async with uow:
        for job_view in jobs:
            if job_view.ai is None:
                continue
            try:
                async with uow.savepoint():
                    if job_view.is_hidden():
                        await uow.db.create(job_view)
                    else:
                        await uow.db.create(
                            ActiveJob(job_data=job_view),
                        )
            except AlreadyExistsError:
                pass


async def collect_pipeline(http_client, llm, uow) -> dict[int, ProjectPageData]:
    seen_external_ids, pending_analyze, page_cache = set(), [], {}
    async with uow:
        async for feed_name, job in fetch_jobs(http_client):
            if job.external_id in seen_external_ids:
                continue
            seen_external_ids.add(job.external_id)
            try:
                async with uow.savepoint():
                    await uow.db.read_one(JobView, external_id=job.external_id, with_raise=True)
            except NotFoundError:
                html_page = await http_client.fetch_project_page(job.url)
                page_data = parse_fl_job_page(html_page)
                if not page_data.is_closed:
                    job.description, job.feed_name, job.budget_text = page_data.description, feed_name, page_data.budget_text
                    page_cache[job.external_id] = page_data
                    if analyze_basic(job):
                        pending_analyze.append(JobView(job=job))

    await llm.analyze_batch(pending_analyze)
    await save_analyzed_jobs(uow=uow, jobs=pending_analyze)
    return page_cache


async def read_active_jobs(
    http_client,
    uow,
    page_cache: dict[int, ProjectPageData] | None = None,
) -> list[JobView]:
    page_cache = page_cache or {}

    # job_data уже подгружается через lazy="joined"
    async with uow:
        active_jobs = await uow.db.read(ActiveJob)
    valid_jobs: list[JobView] = []

    for job_view in active_jobs:
        external_id = job_view.job.external_id
        page_data = page_cache.get(external_id)
        if page_data is None:
            html_page = await http_client.fetch_project_page(job_view.job.url)
            page_data = parse_fl_job_page(html_page)

        if not page_data.is_closed:
            fetch_data = await http_client.fetch_offer_range(project_id=external_id)
            fetch_data_dto = offer_range(fetch_data)
            full_project_data = ProjectData(page_data=page_data, offer_range=fetch_data_dto)

            log.debug("in read page_data: %s", full_project_data)
            job_view.page_data = full_project_data

            valid_jobs.append(job_view)

    valid_jobs.sort(
        key=lambda job_view: job_view.final_priority,
        reverse=True,
    )

    return valid_jobs


async def load_jobs(http_client, llm, uow) -> list[JobView]:
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
