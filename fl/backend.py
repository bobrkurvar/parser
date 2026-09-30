from fl.adapters.http_client import HttpClient
from fl.adapters.llm import AIAnalyzer
from adapters.uow import UnitOfWork
from fl.db.mapper import registry
from fl.jobs import load_jobs, read_active_jobs
from .config import conf
from adapters.db_provider import DbProvider
from fl.dto import JobStaticData
from async_runtime import AsyncRuntime
from datetime import datetime

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

    def update_match(
        self,
        job: JobStaticData,
        matches_profile: bool,
        callback,
    ):
        async def task_wrapper():
            job.matches_profile = matches_profile
            async with self.uow:
                return await self.uow.db.save(job)

        self.runtime.submit(task_wrapper(), callback)

    def responded(
        self,
        job: JobStaticData,
        callback,
    ):
        async def task_wrapper():
            job.responded_at = datetime.now().astimezone()
            async with self.uow:
                return await self.uow.db.save(job)

        self.runtime.submit(task_wrapper(), callback)

    # def update_match(
    #     self,
    #     job_id: int,
    #     matches_profile: bool,
    #     callback,
    # ):
    #     async def task_wrapper():
    #         async with self.uow:
    #             return await self.uow.db.update(
    #                 JobStaticData,
    #                 {"id": job_id},
    #                 matches_profile=matches_profile,
    #             )
    #
    #     self.runtime.submit(task_wrapper(), callback)


    async def close(self):
        await self.client.close()
        await self._db_provider.close()

