from adapters.db_provider import DbProvider
from .adapters.llm import AIAnalyzer
from adapters.uow import UnitOfWork
from hh.adapters.http_client import HttpClient
from .config import conf
from .db.mapper import registry
from .dto import Vacancy
from .use_cases import load_vacancies
from async_runtime import AsyncRuntime


class AsyncBackend:
    def __init__(self, queries: list[str], ai_provider, runtime: AsyncRuntime):
        self.runtime = runtime
        self.queries = queries
        self.ai_provider=ai_provider
        self.client = HttpClient()
        self.llm = AIAnalyzer(ai_provider=self.ai_provider)
        self._db_provider = DbProvider(url=conf.db_url)
        self.uow = UnitOfWork(
            registry=registry,
            provider=self._db_provider,
        )

    def load_vacancies(self, callback) -> None:
        """
        Получает новые вакансии с HH, сохраняет их в БД
        и возвращает вакансии из БД.
        """

        async def task_wrapper():
            return await load_vacancies(
                client=self.client,
                uow=self.uow,
                queries=self.queries,
                llm=self.llm,
            )

        self.runtime.submit(
            task_wrapper(),
            callback,
        )

    def read_vacancies(self, callback) -> None:
        """
        Читает сохранённые вакансии без запросов к HH и Gemini.
        """

        async def task_wrapper():
            async with self.uow:
                return await self.uow.db.read(
                    Vacancy,
                    is_hidden=False,
                    loaded="ai_analysis",
                )

        self.runtime.submit(
            task_wrapper(),
            callback,
        )

    def update_hidden(
        self,
        vacancy_id: int,
        hidden: bool,
        callback,
    ) -> None:
        async def task_wrapper():
            async with self.uow:
                return await self.uow.db.update(
                    Vacancy,
                    {"id": vacancy_id},
                    hidden=hidden,
                )

        self.runtime.submit(
            task_wrapper(),
            callback,
        )

    async def close(self) -> None:
        await self.client.close()
        await self._db_provider.close()
