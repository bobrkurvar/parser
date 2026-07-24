import asyncio
from functools import partial
from dto import FeedJob, JobStaticData
from exceptions import RateLimitError, ResourceNotFoundError
import logging

log = logging.getLogger(__name__)

def get_job_url(job: JobStaticData | FeedJob) -> str:
    return job.feed_job.url if isinstance(job, JobStaticData) else job.url

async def get_pages(client, jobs: list[JobStaticData | FeedJob], batch_size: int = 20, static: bool = False):
    # async def fetch_with_context(job: JobStaticData | FeedJob):
    #     url = job.feed_job.url if isinstance(job, JobStaticData) else job.url
    #     html = await client.fetch_project_page(url)
    #     return job, html

    tasks_to_run = [
        (job, partial(client.fetch_project_page, get_job_url(job)))
        for job in jobs
    ]

    return await execute_batch(tasks_to_run, batch_size, static)



async def get_offer_data(client, jobs: list[JobStaticData], batch_size: int = 20, static: bool = False):
    # async def fetch_with_context(job: JobStaticData):
    #     offer_data = await client.fetch_offer_range(project_id=job.feed_job.external_id)
    #     return job, offer_data

    tasks_to_run = [
        (job, partial(client.fetch_offer_range, project_id=job.feed_job.external_id))
        for job in jobs
    ]

    return await execute_batch(tasks_to_run, batch_size, static)


async def execute_batch(factories: list, batch_size: int = 10, static: bool = False):
    pending = factories
    successful_results = []
    failed_results = []

    max_size = batch_size if static else None

    while pending:
        successful_count = 0
        rate_limit_hit = False
        items_to_retry = []

        batch = pending[:batch_size]

        results = await asyncio.gather(
            *(factory() for context, factory in batch),
            return_exceptions=True,
        )

        for (context, factory), result in zip(batch, results):
            if isinstance(result, RateLimitError):
                rate_limit_hit = True
                items_to_retry.append((context, factory))

            elif isinstance(result, ResourceNotFoundError):
                failed_results.append(context)

            elif isinstance(result, Exception):
                log.warning(
                    "Ошибка выполнения задачи %s: %s",
                    factory,
                    result,
                    exc_info=(type(result), result, result.__traceback__),
                )

            else:
                successful_results.append(result)
                successful_count += 1

        if rate_limit_hit:
            max_size = successful_count or 1

        pending = items_to_retry + pending[batch_size:]
        batch_size = max_size if max_size is not None else batch_size + 2
        sleep_time = 1 if rate_limit_hit else 0.3
        await asyncio.sleep(sleep_time)

    return successful_results, failed_results
