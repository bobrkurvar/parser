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
    def __init__(self, retry_on = (), decrease_on = (), max_retries=3, increase = 2):
        self.retry_on = retry_on
        self.max_retries = max_retries
        self.decrease_on = decrease_on
        self.increase = increase

    async def collect_all(
        self,
        factories: list,
        batch_size: int = 10,
        static: bool = False,
    ):
        return await self._execute(
            factories=factories,
            stop_on_error=False,
            batch_size=batch_size,
            static=static,
        )

    async def collect_until_error(
        self,
        factories: list,
        batch_size: int = 10,
        static: bool = False,
        with_raise = True,
    ):
        return await self._execute(
            factories=factories,
            stop_on_error=True,
            with_raise = with_raise,
            batch_size=batch_size,
            static=static,
        )


    async def _execute(
        self,
        factories: list,
        stop_on_error: bool,
        batch_size: int = 10,
        static: bool = False,
        with_raise: bool = False,
    ):
        pending = factories
        successful_results, failed_results = [], []

        while pending:
            successful_count = 0
            to_decrease = False
            items_to_retry = []
            stop = False

            batch = pending[:batch_size]

            tasks = [
                asyncio.create_task(factory())
                for factory in batch
            ]

            for completed in asyncio.as_completed(tasks):
                factory, result = await completed
                context = factory.context

                if isinstance(result, self.retry_on):
                    if isinstance(result, self.decrease_on):
                        to_decrease = True

                    if (
                            self.max_retries is None
                            or factory.tries <= self.max_retries
                    ):
                        items_to_retry.append(factory)
                        continue

                if isinstance(result, Exception):
                    failed_results.append((context, result))

                    if stop_on_error:
                        if with_raise:
                            for task in tasks:
                                if not task.done():
                                    task.cancel()

                            await asyncio.gather(
                                *tasks,
                                return_exceptions=True,
                            )

                            raise result

                        stop = True

                    continue

                successful_count += 1
                successful_results.append((context, result))

            if stop:
                break

            pending = pending[len(batch):] + items_to_retry

            if not static:
                if to_decrease:
                    batch_size = successful_count or 1
                else:
                    batch_size += self.increase

            await asyncio.sleep(0.3)

        return successful_results, failed_results

    # async def _execute(self, factories: list, stop_on_error: bool, batch_size: int = 10, static: bool = False, with_raise=False):
    #     pending = factories
    #     successful_results, failed_results = [], []
    #
    #     while pending:
    #         successful_count = 0
    #         to_decrease = False
    #         items_to_retry = []
    #         batch = pending[:batch_size]
    #
    #         tasks = [
    #             asyncio.create_task(factory())
    #             for factory in batch
    #         ]
    #
    #         for completed in asyncio.as_completed(tasks):
    #             factory, result = await completed
    #             context = factory.context
    #             if isinstance(result, self.retry_on):
    #                 if isinstance(result, self.decrease_on):
    #                     to_decrease = True
    #                 if self.max_retries is None or factory.tries <= self.max_retries:
    #                     items_to_retry.append(factory)
    #                     continue
    #
    #             if isinstance(result, Exception):
    #                 failed_results.append((context, result))
    #                 if stop_on_error:
    #                     for task in tasks:
    #                         if not task.done():
    #                             task.cancel()
    #
    #                     await asyncio.gather(
    #                         *tasks,
    #                         return_exceptions=True,
    #                     )
    #                     if with_raise:
    #                         raise result
    #                     else:
    #                         return successful_results, failed_results
    #
    #                 #failed_results.append((context, result))
    #                 continue
    #
    #             successful_count += 1
    #             successful_results.append((context, result))
    #
    #
    #         pending = pending[len(batch):] + items_to_retry
    #
    #         if not static:
    #             if to_decrease:
    #                 batch_size = successful_count or 1
    #             else:
    #                 batch_size += self.increase
    #
    #         await asyncio.sleep(0.3)
    #
    #     return successful_results, failed_results
