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
        self.key_manager = KeyProvider()
        self.api_key = self.key_manager.get_key()
        self.client = genai.Client(api_key=self.api_key)
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

    def _swap_api_key(self):
        log.debug("swap key")
        self.api_key = self.key_manager.get_key()
        self.client = genai.Client(api_key=self.api_key)

    def _build_batch_text(self, chunk: list[FeedJob]) -> str:
        batch_text_parts: list[str] = []

        for index, job in enumerate(chunk):
            batch_text_parts.append(
                f"ID: {index}\n"
                f"Заголовок: {job.title}\n"
                f"Описание: {job.description}"
            )

        return "\n---\n".join(batch_text_parts)

    async def _request_batch(self, batch_text: str):
        try:
            response = await self.client.aio.models.generate_content(
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

            return response.parsed

        except Exception:
            log.exception("Ошибка Gemini")
            self._swap_api_key()
            await asyncio.sleep(2)

        return None

    async def analyze_jobs(
        self,
        jobs_to_analyze: list[FeedJob],
        batch_size: int = 15,
    ) -> list[AIAnalysis]:
        result: list[AIAnalysis | None] = [None] * len(jobs_to_analyze)

        for chunk_number, start_index in enumerate(range(0, len(jobs_to_analyze), batch_size)):
            if self.limit is not None and chunk_number >= self.limit:
                break

            chunk = jobs_to_analyze[start_index:start_index + batch_size]
            batch_text = self._build_batch_text(chunk)

            ai_results = await self._request_batch(batch_text)

            if ai_results is None:
                log.error("Не удалось обработать пачку из %s заказов.",len(chunk))
                continue

            for ai_data in ai_results:
                if not 0 <= ai_data.batch_index < len(chunk):
                    log.error("Несуществующий batch_index: %s",ai_data.batch_index)
                    continue

                priority_value = max(JobPriority.HIDDEN, min(ai_data.priority_value, JobPriority.HIGH))

                result[start_index + ai_data.batch_index] = AIAnalysis(
                    priority=JobPriority(priority_value),
                    explanation=ai_data.explanation,
                    confidence=ai_data.confidence,
                )

            await asyncio.sleep(1)

        return result

