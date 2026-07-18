import asyncio
from functools import partial
from dto import FeedJob, JobStaticData, RateLimitError, NotFoundError

async def get_pages(client, jobs: list[JobStaticData | FeedJob], batch_size: int = 20, static: bool = False):
    async def fetch_with_context(job: JobStaticData | FeedJob):
        url = job.feed_job.url if isinstance(job, JobStaticData) else job.url
        html = await client.fetch_project_page(url)
        return job, html

    tasks_to_run = [
        (job, partial(fetch_with_context, job))
        for job in jobs
    ]

    return await execute_batch(tasks_to_run, batch_size, static)


async def get_offer_data(client, jobs: list[JobStaticData], batch_size: int = 20, static: bool = False):
    async def fetch_with_context(job: JobStaticData):
        offer_data = await client.fetch_offer_range(project_id=job.feed_job.external_id)
        return job, offer_data

    tasks_to_run = [
        (job, partial(fetch_with_context, job))
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

            elif isinstance(result, NotFoundError):
                failed_results.append(context)

            elif isinstance(result, Exception):
                pass

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

# async def execute_batch(factories: list, batch_size: int = 10, static: bool = False):
#     # tasks_to_run = [
#     #     partial(client.get_vacancy, vac.id)
#     #     for vac in vacancies
#     # ]
#     # такого рода фабрики передаются в cors потому что при cancel корутина умирает
#     pending, successful_results, failed_results = factories, [], []
#     max_size = batch_size if static else None
#     while pending:
#         successful_count, rate_limit_hit, items_to_retry, batch = 0, False, [], pending[:batch_size]
#         task_to_context_factory = {
#             asyncio.create_task(factory()): (context, factory)
#             for context, factory in batch
#         }
#         done, pending_tasks = await asyncio.wait(task_to_context_factory.keys(), return_when=asyncio.FIRST_EXCEPTION)
#         for task in done:
#             context, factory = task_to_context_factory[task]
#             try:
#                 result = task.result()
#                 successful_results.append(result)
#                 successful_count += 1
#             except RateLimitError:
#                 rate_limit_hit = True
#                 items_to_retry.append((context, factory))
#             except NotFoundError:
#                 failed_results.append(context)
#             except:
#                 pass
#         for task in pending_tasks:
#             #task.cancel()
#             #items_to_retry.append(task_to_context_factory[task])
#         # Гасим предупреждения об отмененных задачах - после cancel сами запросы не выполнятся, просто graceful shutdown для cancell
#         if pending_tasks:
#             await asyncio.gather(*pending_tasks, return_exceptions=True)
#         if rate_limit_hit:
#             max_size = successful_count or 1
#         pending = items_to_retry + pending[batch_size:]
#         batch_size = max_size if max_size is not None else batch_size + 2
#         sleep_time = 1 if rate_limit_hit else 0.3
#         await asyncio.sleep(sleep_time)
#     return successful_results, failed_results