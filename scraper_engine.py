import asyncio
from functools import partial
from dto import FeedJob

async def get_pages(client, jobs: list[FeedJob], batch_size: int = 5, static: bool = False):
    async def fetch_with_context(job):
        html = await client.fetch_project_page(job.url)
        return job, html

    tasks_to_run = [
        partial(fetch_with_context, job)
        for job in jobs
    ]

    return await execute_batch(tasks_to_run, batch_size, static)


async def execute_batch(factories: list, batch_size: int = 5, static: bool = False):
    # tasks_to_run = [
    #     partial(client.get_vacancy, vac.id)
    #     for vac in vacancies
    # ]
    # такого рода фабрики передаются в cors потому что при cancel корутина умирает
    pending, successful_results = factories, []
    max_size = batch_size if static else None
    while pending:
        successful_count, rate_limit_hit, items_to_retry, batch = 0, False, [], pending[:batch_size]
        task_to_factory = {
            asyncio.create_task(factory()): factory
            for factory in batch
        }
        done, pending_tasks = await asyncio.wait(task_to_factory.keys(), return_when=asyncio.FIRST_EXCEPTION)
        for task in done:
            try:
                result = task.result()
                successful_results.append(result)
                successful_count += 1
            except Exception:
                rate_limit_hit = True
                items_to_retry.append(task_to_factory[task])
        for task in pending_tasks:
            task.cancel()
            items_to_retry.append(task_to_factory[task])
        # Гасим предупреждения об отмененных задачах - после cancel сами запросы не выполнятся, просто graceful shutdown для cancell
        if pending_tasks:
            await asyncio.gather(*pending_tasks, return_exceptions=True)
        if rate_limit_hit:
            max_size = successful_count or 1
        pending = items_to_retry + pending[batch_size:]
        batch_size = max_size if max_size is not None else batch_size + 2
        sleep_time = 1 if rate_limit_hit else 0.3
        await asyncio.sleep(sleep_time)
    return successful_results