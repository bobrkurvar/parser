import asyncio
import threading
from adapters.web import HttpClient
from adapters.llm import GeminiAnalyzer
from adapters.uow import UnitOfWork
from db.mapper import registry
from jobs import load_jobs, read_active_jobs
from core import conf
from adapters.db_provider import DbProvider
from dto import JobView


class AsyncBackend:
    def __init__(self):
        self.loop = asyncio.new_event_loop()
        self.client = None
        self.llm = None
        self._db_provider = None
        self.uow = None
        self.is_ready = threading.Event()  # Сигнал готовности зависимостей

        # Запускаем поток-воркер
        self.thread = threading.Thread(target=self._run_event_loop, daemon=True)
        self.thread.start()

    # @property
    # def db(self):
    #     self._uow = UnitOfWork(registry=registry, provider=self.db_provider)
    #     return self._uow.db

    def _run_event_loop(self):
        """Метод выполняется в отдельном потоке."""
        asyncio.set_event_loop(self.loop)

        # Инициализируем зависимости ВНУТРИ цикла
        self.client = HttpClient()
        self.llm = GeminiAnalyzer()
        self._db_provider = DbProvider(url=conf.db_url)
        self.uow = UnitOfWork(registry=registry, provider=self._db_provider)

        # Сообщаем основному потоку, что мы готовы
        self.is_ready.set()

        # Запускаем бесконечный цикл
        self.loop.run_forever()


    def run_task(self, coro, callback):
        """
        Отправляет корутину на выполнение в поток asyncio.
        callback будет вызван в потоке Tkinter (через .after)
        """

        def done_callback(fut):
            try:
                result = fut.result()
                # Передаем результат в главный поток через очередь событий Tkinter
                callback(result)
            except Exception as e:
                callback(e)

        # Безопасно планируем задачу в чужом цикле событий
        future = asyncio.run_coroutine_threadsafe(coro, self.loop)
        future.add_done_callback(done_callback)


    def load_jobs(self, callback):
        async def task_wrapper():
            return await load_jobs(http_client=self.client, llm=self.llm, uow=self.uow)

        self.run_task(task_wrapper(), callback)


    def refresh_active_jobs(self, callback) -> None:
        """
        Только активные вакансии из БД:
        без RSS и без Gemini.
        """
        async def task_wrapper():
            return await read_active_jobs(http_client=self.client, uow=self.uow)

        self.run_task(task_wrapper(), callback)


    def human_priority(self, external_id: int, mark: int | str, callback):
        async def task_wrapper():
            async with self.uow:
                return await self.uow.db.update(JobView, filters={"external_id": external_id}, human_priority=int(mark))
        self.run_task(task_wrapper(), callback)


    async def _shutdown_resources(self):
        """Асинхронно закрывает все соединения и отменяет задачи."""
        # 1. Отменяем все активные задачи в этом цикле, кроме текущей
        tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
        for task in tasks:
            task.cancel()

        if tasks:
            # Даем задачам шанс корректно завершиться после отмены
            await asyncio.gather(*tasks, return_exceptions=True)

        # 2. Закрываем HttpClient
        if self.client:
            await self.client.close()

        # 3. Закрываем БД (ИСПРАВЛЕНА ТВОЯ ОПЕЧАТКА: было self.client.close())
        if self._db_provider:
            try:
                # Убедись, что в DbProvider есть асинхронный метод close/dispose
                await self._db_provider.engine.dispose()
            except Exception as e:
                print(f"Ошибка при закрытии dbProvider: {e}")

    def stop(self):
        """Корректное завершение работы потока и ресурсов."""
        if not self.loop.is_running():
            return

        # 1. Отправляем корутину очистки в цикл и ЖДЕМ её результата
        future = asyncio.run_coroutine_threadsafe(self._shutdown_resources(), self.loop)

        try:
            # Блокируем основной поток (Tkinter) максимум на 3 секунды,
            # чтобы дать соединениям закрыться изящно
            future.result(timeout=3.0)
        except TimeoutError:
            print("Таймаут при закрытии ресурсов (некоторые сокеты могли остаться открытыми).")
        except Exception as e:
            print(f"Исключение при выходе: {e}")

        # 2. Теперь безопасно останавливаем цикл
        self.loop.call_soon_threadsafe(self.loop.stop)

        # 3. Ждем, пока поток-воркер действительно завершится
        if self.thread.is_alive():
            self.thread.join(timeout=2.0)
