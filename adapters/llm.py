from google import genai
from pydantic import BaseModel, Field
from dto import AIAnalysis, JobPriority, FeedJob
import asyncio
import logging
from .files import KeyProvider
import textwrap

log = logging.getLogger(__name__)

TARGET_TECHNOLOGIES = [
    "Python",
    "FastAPI",
    "Django",
    "Flask",
    "SQLAlchemy",
    "TaskIQ",
    "Telegram Bot API",
    "Aiogram",
    "Selenium",
    "Scrapy",
    "Pandas",
    "REST API",
]

class GeminiSchema(BaseModel):
    batch_index: int = Field(description="Номер заказа из поля ID во входной пачке.")
    priority_value: int = Field(description="Итоговый приоритет заказа: 0 — HIDDEN, 1 — LOW, 2 — MEDIUM, 3 — HIGH.")
    explanation: str = Field(
        description=(
            "Кратко объясни выбранный приоритет на русском языке. "
            "Укажи только решающие признаки из текста заказа. "
            "Не приписывай заказу технологии, функциональность "
            "или ограничения, которых в описании нет."
        ),
    )
    confidence: float = Field(
        description=(
            "Уверенность от 0.0 до 1.0 в том, что выбран именно верный "
            "приоритет на основании текста заказа. "
            "Это не оценка бюджета, качества заказа, его сложности "
            "или вероятности написания кода. "
            "0.90–1.00 используй только при прямых и однозначных признаках "
            "категории. "
            "Если описание неполное, допускает несколько приоритетов "
            "или вывод основан на косвенных признаках — используй значение "
            "ниже 0.90. Не ставь 1.00 по умолчанию."
        ),
    )


class GeminiAnalyzer:
    def __init__(self):
        self._pool = asyncio.Queue()
        self.key_manager = KeyProvider()
        self._background_tasks = set()
        for key in self.key_manager.keys:
            self._pool.put_nowait(genai.Client(api_key=key))
        #self.api_key = self.key_manager.get_key()
        #self.client = genai.Client(api_key=self.api_key)
        target_technologies = ", ".join(TARGET_TECHNOLOGIES)

        self.system_instruction = textwrap.dedent(f"""
            ОБЯЗАТЕЛЬНОЕ ПРАВИЛО: Всегда отвечай только на русском языке.

            Ты оцениваешь заказы для Python backend-разработчика.

            Оценивай конкретную работу, которую должен выполнить исполнитель,
            а не весь продукт, упомянутый в заказе.

            Если заказ смешанный, выбирай приоритет по основной работе
            и основному результату для исполнителя. Не предполагай отсутствующую
            backend-часть и не повышай приоритет из-за второстепенных деталей
            продукта.

            Целевые технологии разработчика:
            {target_technologies}

            Сопоставь заказ с критериями HIGH, MEDIUM, LOW и HIDDEN
            и выбери один наиболее подходящий приоритет.

            КРИТЕРИИ ПРИОРИТЕТА:

            3 (HIGH):
            - Для выполнения работы явно требуется одна или несколько целевых
              технологий, перечисленных выше. Технология должна быть нужна
              исполнителю, а не просто упоминаться как часть существующего продукта.
            - Создание или программная доработка бота, парсера, скрипта,
              автоматизации или пайплайна.
            - Основной результат — собственный backend API, backend-сервис,
              внутренняя система, серверная часть продукта или другой
              самостоятельный backend-функционал.
            - Из заказа прямо следует разработка серверной логики, например:
              авторизация, роли, личный кабинет, платежи, бизнес-процессы,
              хранение и обработка данных, CRM/ERP-логика или нестандартный
              функционал.

            2 (MEDIUM):
            - Задача с большой вероятностью потребует разработки кодом,
              но прямых оснований для HIGH недостаточно.
            - Многостраничный сайт, сайт компании, корпоративный сайт,
              каталог, интернет-магазин, веб-приложение, сервис или MVP,
              когда из заказа не следует, что работа ограничена готовым
              конструктором, CMS, шаблоном или темой.
            - Веб-разработка, где код вероятен, но основная backend-часть
              или целевой стек не подтверждены текстом заказа.

            1 (LOW):
            - Заказ связан с разработкой, но признаков самостоятельной
              кастомной разработки мало.
            - Одностраничник, простой лендинг, отдельная страница,
              мелкие правки, работа с блоками или существующим сайтом.
            - Интеграция существующего сайта, магазина, CRM или сервиса
              с внешним API, когда из заказа не следует, что нужно создать
              отдельный backend-сервис или работать на целевом стеке.
            - Работа может потребовать кода, но из текста это следует слабо
              или остаётся неясным.

            0 (HIDDEN):
            - Заказ по смыслу не подходит Python backend-разработчику,
              даже если формально относится к IT.
            - Основная работа — frontend-разработка, вёрстка, дизайн
              или другое непрофильное направление без backend-разработки.
            - Заказ относится к data science, machine learning,
              разработке для устройств или другому направлению,
              не относящемуся к backend-профилю.
            - Требуется дорабатывать существующий проект на явно нецелевом
              языке, фреймворке или платформе.
            - Требуется настройка, установка, аудит, администрирование
              или обслуживание готового ПО без разработки собственного продукта.
            - В заказе прямо указаны конструктор сайтов, готовая CMS,
              готовая платформа, шаблон или тема:
              Tilda, WordPress, Bitrix, Webasyst, Wix и подобное.
            - Дизайн без разработки, контент, копирайтинг, SEO без разработки,
              SMM, реклама, ручной ввод данных, поиск исполнителей,
              консультации без реализации и подобные задачи.

            ВАЖНОЕ УТОЧНЕНИЕ:

            Слова «сайт», «по ТЗ», «движок», «сайт под ключ»,
            «корпоративный сайт» сами по себе не доказывают использование
            конструктора, CMS или конкретного стека.
        """).strip()
        self.limit = None

    # def _swap_api_key(self):
    #     log.debug("swap key")
    #     self.api_key = self.key_manager.get_key()
    #     self.client = genai.Client(api_key=self.api_key)

    def _build_batch_text(self, chunk: list[tuple[str, str]]) -> str:
        batch_text_parts: list[str] = []

        for index, (title, description) in enumerate(chunk):
            batch_text_parts.append(
                f"ID: {index}\n"
                f"Заголовок: {title}\n"
                f"Описание: {description}"
            )

        return "\n---\n".join(batch_text_parts)

    async def _cooldown_client(self, client: genai.Client):
        log.warning("Ключ поймал ошибку (вероятно 429). Уходит на паузу 60 сек...")
        await asyncio.sleep(60)
        self._pool.put_nowait(client)
        log.debug("Ключ вернулся в пул.")

    async def _process_single_chunk(self, chunk: list[tuple[str, str]], start_index: int) -> list[tuple[int, AIAnalysis]]:
        """Изолированная задача для обработки одной пачки данных."""
        batch_text, retries = self._build_batch_text(chunk), 0

        while retries < 5:
            client = await self._pool.get()
            try:
                response = await client.aio.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=(
                        "Проанализируй следующие заказы "
                        "и верни массив JSON:\n"
                        f"{batch_text}"
                    ),
                    config={
                        "system_instruction": self.system_instruction,
                        "response_mime_type": "application/json",
                        "response_schema": list[GeminiSchema],
                    },
                )

                if not response.parsed:
                    raise RuntimeError("Gemini вернул пустой ответ или сработал фильтр.")

                parsed_results = []
                for ai_data in response.parsed:
                    if not 0 <= ai_data.batch_index < len(chunk):
                        log.error("Несуществующий batch_index: %s", ai_data.batch_index)
                        continue

                    priority_value = max(JobPriority.HIDDEN, min(ai_data.priority_value, JobPriority.HIGH))

                    analysis_obj = AIAnalysis(
                        priority=JobPriority(priority_value),
                        explanation=ai_data.explanation,
                        confidence=ai_data.confidence,
                    )

                    absolute_index = start_index + ai_data.batch_index
                    parsed_results.append((absolute_index, analysis_obj))

                self._pool.put_nowait(client)
                return parsed_results

            except Exception:
                log.exception("Ошибка запроса к Gemini.")
                retries += 1
                task = asyncio.create_task(self._cooldown_client(client))
                self._background_tasks.add(task)
                task.add_done_callback(self._background_tasks.discard)
                await asyncio.sleep(0)

        log.error("Пачка заказов (индекс %s) пропущена после %s неудачных попыток.", start_index, retries)
        return []

    async def analyze_jobs(
        self,
        jobs_to_analyze: list[FeedJob],
        batch_size: int = 15,
    ) -> list[AIAnalysis]:
        if not jobs_to_analyze:
            return []

        result: list[AIAnalysis | None] = [None] * len(jobs_to_analyze)
        tasks = []

        for chunk_number, start_index in enumerate(range(0, len(jobs_to_analyze), batch_size)):
            if self.limit is not None and chunk_number >= self.limit:
                break

            chunk = jobs_to_analyze[start_index:start_index + batch_size]
            tasks.append(self._process_single_chunk(chunk, start_index))

        results = await asyncio.gather(*tasks)
        for chunk_result in results:
            for absolute_index, analysis_obj in chunk_result:
                result[absolute_index] = analysis_obj

        return result
    #async def _request_batch(self, batch_text: str):
    #     try:
    #         response = await self.client.aio.models.generate_content(
    #             model="gemini-2.5-flash",
    #             contents=(
    #                 "Проанализируй следующие заказы "
    #                 "и верни массив JSON:\n"
    #                 f"{batch_text}"
    #             ),
    #             config={
    #                 "system_instruction": self.system_instruction,
    #                 "response_mime_type": "application/json",
    #                 "response_schema": list[GeminiSchema],
    #             },
    #         )
    #
    #         if not response.parsed:
    #             raise RuntimeError("Gemini вернул пустой ответ или сработал фильтр.")
    #
    #         return response.parsed
    #
    #     except Exception:
    #         log.exception("Ошибка Gemini")
    #         self._swap_api_key()
    #         await asyncio.sleep(2)
    #
    #     return None
    #
    # async def analyze_jobs(
    #     self,
    #     jobs_to_analyze: list[FeedJob],
    #     batch_size: int = 15,
    # ) -> list[AIAnalysis]:
    #     result: list[AIAnalysis | None] = [None] * len(jobs_to_analyze)
    #
    #     for chunk_number, start_index in enumerate(range(0, len(jobs_to_analyze), batch_size)):
    #         if self.limit is not None and chunk_number >= self.limit:
    #             break
    #
    #         chunk = jobs_to_analyze[start_index:start_index + batch_size]
    #         batch_text = self._build_batch_text(chunk)
    #
    #         ai_results = await self._request_batch(batch_text)
    #
    #         if ai_results is None:
    #             log.error("Не удалось обработать пачку из %s заказов.",len(chunk))
    #             continue
    #
    #         for ai_data in ai_results:
    #             if not 0 <= ai_data.batch_index < len(chunk):
    #                 log.error("Несуществующий batch_index: %s",ai_data.batch_index)
    #                 continue
    #
    #             priority_value = max(JobPriority.HIDDEN, min(ai_data.priority_value, JobPriority.HIGH))
    #
    #             result[start_index + ai_data.batch_index] = AIAnalysis(
    #                 priority=JobPriority(priority_value),
    #                 explanation=ai_data.explanation,
    #                 confidence=ai_data.confidence,
    #             )
    #
    #         await asyncio.sleep(1)
    #
    #     return result

