from google import genai
from pydantic import BaseModel, Field
from dto import AIAnalysis, JobPriority, JobView
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

            К подходящим задачам backend-профиля относятся серверная разработка,
            боты, скрипты, парсинг, автоматизация, API-интеграции, пайплайны,
            CRM/ERP, базы данных, внутренние системы и веб-разработка,
            где требуется backend или собственная логика.

            Целевые технологии разработчика:
            {target_technologies}

            Сопоставь заказ с критериями HIGH, MEDIUM, LOW и HIDDEN
            и выбери один наиболее подходящий приоритет.

            КРИТЕРИИ ПРИОРИТЕТА:

            3 (HIGH):
            - В заказе требуется одна или несколько целевых технологий,
              перечисленных выше, и это относится именно к работе исполнителя.
            - Разработка бота, парсера, скрипта или автоматизации.
            - Из описания с очень высокой вероятностью следует необходимость
              кастомной разработки кодом: backend, база данных, авторизация,
              личный кабинет, роли пользователей, платежи, CRM/ERP,
              веб-сервис, внутренняя система, нестандартная бизнес-логика
              или другой собственный функционал.

            2 (MEDIUM):
            - Задача с большой вероятностью будет решаться разработкой кодом,
              но прямых признаков для HIGH недостаточно.
            - Многостраничный сайт, сайт компании, корпоративный сайт,
              каталог, интернет-магазин, веб-приложение, сервис, MVP
              или другая веб-разработка, которая с большей вероятностью
              требует кода, чем конструктора.
            - API-интеграции.
            - Из описания не следует, что работа выполняется на конструкторе,
              готовой CMS, шаблоне, теме или другой готовой платформе.

            1 (LOW):
            - Заказ связан с разработкой, но признаков полноценной
              кастомной разработки мало.
            - Одностраничник, простой лендинг, отдельная страница,
              мелкие правки сайта, работа с блоками или существующим сайтом.
            - Задача может быть выполнена кодом, но из описания это
              не следует с достаточной вероятностью.

            0 (HIDDEN):
            - Заказ по смыслу не подходит разработчику, даже если формально
              попал в техническую категорию.
            - Заказ направлен на frontend-разработку, вёрстку или дизайн
              без backend-разработки.
            - Дизайн без разработки, контент, копирайтинг, SEO без разработки,
              SMM, реклама, ручной ввод данных, поиск исполнителей,
              консультации без реализации и подобные задачи.
            - В заказе прямо указаны конструктор сайтов, готовая CMS,
              готовая платформа, шаблон или тема:
              Tilda, WordPress, Bitrix, Webasyst, Wix и подобное.

            ВАЖНЫЕ ПРАВИЛА:
        
            1. Упоминание целевой технологии даёт HIGH только тогда,
               когда она требуется от исполнителя или относится к реализации
               задачи, а не названа вскользь.

            2. Слова «сайт», «по ТЗ», «движок», «сайт под ключ»,
               «корпоративный сайт» сами по себе не доказывают использование
               конструктора, CMS или конкретного стека.
        """).strip()
        self.limit = None

    def _swap_api_key(self):
        log.debug("swap key")
        self.api_key = self.key_manager.get_key()
        self.client = genai.Client(api_key=self.api_key)


    def _build_batch_text(self, chunk: list[JobView]) -> tuple[dict[int, JobView], str]:
        jobs_by_index: dict[int, JobView] = {}
        batch_text_parts: list[str] = []

        for index, job_view in enumerate(chunk):
            jobs_by_index[index] = job_view

            batch_text_parts.append(
                f"ID: {index}\n"
                f"Заголовок: {job_view.job.title}\n"
                f"Описание: {job_view.job.description}"
            )
        return jobs_by_index, "\n---\n".join(batch_text_parts)


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


    async def analyze_batch(
        self,
        jobs_to_analyze: list[JobView],
        batch_size: int = 15,
    ):
        chunks = [
            jobs_to_analyze[i:i + batch_size]
            for i in range(0, len(jobs_to_analyze), batch_size)
        ]

        chunks = chunks[:self.limit]

        for chunk in chunks:
            jobs_by_index, batch_text = self._build_batch_text(chunk)

            ai_results = await self._request_batch(batch_text)

            if ai_results is None:
                log.error("Не удалось обработать пачку из %s заказов.",len(chunk))
                continue

            for ai_data in ai_results:
                job_view = jobs_by_index.get(ai_data.batch_index)

                if job_view is None:
                    log.warning("Gemini вернул несуществующий batch_index: %s",ai_data.batch_index,)
                    continue

                priority_value = max(
                    JobPriority.HIDDEN,
                    min(ai_data.priority_value, JobPriority.HIGH),
                )

                job_view.ai = AIAnalysis(
                    priority=JobPriority(priority_value),
                    explanation=ai_data.explanation,
                    #tech_tags=ai_data.tech_tags,
                    confidence=ai_data.confidence,
                )

            await asyncio.sleep(2)

