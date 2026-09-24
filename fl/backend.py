from fl.adapters.http_client import HttpClient
from fl.adapters.llm import AIAnalyzer
from adapters.uow import UnitOfWork
from fl.db.mapper import registry
from fl.jobs import load_jobs, read_active_jobs
from .config import conf
from adapters.db_provider import DbProvider
from fl.dto import JobStaticData, JobPriority
from async_runtime import AsyncRuntime


class AsyncBackend:
    def __init__(self, ai_provider, runtime: AsyncRuntime):
        self.runtime = runtime
        self.client = HttpClient()
        self.ai_provider = ai_provider
        self.llm = AIAnalyzer(ai_provider=self.ai_provider)
        self._db_provider = DbProvider(url=conf.db_url)
        self.uow = UnitOfWork(registry=registry, provider=self._db_provider)


    def load_jobs(self, callback):
        async def task_wrapper():
            return await load_jobs(http_client=self.client, llm=self.llm, uow=self.uow)

        self.runtime.submit(task_wrapper(), callback)


    def refresh_active_jobs(self, callback) -> None:
        """
        Только активные вакансии из БД:
        без RSS и без Gemini.
        """
        async def task_wrapper():
            return await read_active_jobs(http_client=self.client, uow=self.uow)

        self.runtime.submit(task_wrapper(), callback)

    def update_priority(
        self,
        job_id: int,
        mark: int | str,
        callback,
    ):
        async def task_wrapper():
            priority = JobPriority(int(mark))

            async with self.uow:
                return await self.uow.db.update(
                    JobStaticData,
                    {"id": job_id},
                    priority=priority.value,
                    is_hidden=priority == JobPriority.HIDDEN,
                )

        self.runtime.submit(task_wrapper(), callback)

    async def close(self):
        await self.client.close()
        await self._db_provider.close()

    # async def _shutdown_resources(self):
    #     """Асинхронно закрывает все соединения и отменяет задачи."""
    #     # 1. Отменяем все активные задачи в этом цикле, кроме текущей
    #     tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
    #     for task in tasks:
    #         task.cancel()
    #
    #     if tasks:
    #         # Даем задачам шанс корректно завершиться после отмены
    #         await asyncio.gather(*tasks, return_exceptions=True)
    #
    #     # 2. Закрываем http_transport
    #     if self.http_transport:
    #         await self.http_transport.close()
    #
    #     if self._db_provider:
    #         try:
    #             await self._db_provider.engine.dispose()
    #         except Exception as e:
    #             print(f"Ошибка при закрытии dbProvider: {e}")
