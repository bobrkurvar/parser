import asyncio
import logging
from functools import partial

log = logging.getLogger(__name__)

class Factory:
    def __init__(self, func, /, *args, context=None, **kwargs):
        self.context = context
        self.func = partial(func, *args, **kwargs)
        self.tries = 0

    async def __call__(self):
        self.tries += 1
        try:
            return self, await self.func()
        except Exception as exc:
            return self, exc


class Scraper:
    def __init__(self, retry_on = (), decrease_on = (), failed_on = (), max_retries=3, increase = 2):
        self.retry_on = retry_on
        self.max_retries = max_retries
        self.decrease_on = decrease_on
        self.increase = increase
        self.failed_on = failed_on



    async def execute_batch(self, factories: list, batch_size: int = 10, static: bool = False):
        pending = factories
        successful_results, failed_results = [], []
        max_size = batch_size if static else None

        while pending:
            successful_count = 0
            to_decrease = False
            items_to_retry = []
            batch = pending[:batch_size]

            results = await asyncio.gather(*(factory() for factory in batch))

            for factory, result in results:
                context = factory.context
                if isinstance(result, self.retry_on):
                    if isinstance(result, self.decrease_on):
                        to_decrease = True
                    if factory.tries <= self.max_retries:
                        items_to_retry.append(factory)
                        continue

                if isinstance(result, self.failed_on):
                    failed_results.append((context, result))
                    continue

                if isinstance(result, Exception):
                    log.warning(
                        "Ошибка выполнения с контекстом: %s и результатом: %s",
                        context,
                        result,
                    )
                    raise result
                else:
                    successful_results.append((context, result))
                    successful_count += 1

            if to_decrease and not static:
                max_size = successful_count or 1

            pending = pending[batch_size:] + items_to_retry
            batch_size = max_size if max_size is not None else batch_size + self.increase
            #sleep_time = 1 if items_to_retry else 0.3
            await asyncio.sleep(0.3)

        return successful_results, failed_results
