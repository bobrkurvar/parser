from google import genai
from pydantic import BaseModel, Field
from dto import AIAnalysis, JobPriority, JobView
import asyncio
import logging
from .files import KeyProvider
import textwrap

log = logging.getLogger(__name__)


# Схема для Gemini
class GeminiSchema(BaseModel):
    origin_id: str = Field(description="Уникальный ID заказа из входного текста")
    is_relevant: bool = Field(description="Подходит ли заказ под веб-разработку?")
    # Мы просим число, которое соответствует твоему JobPriority
    priority_value: int = Field(description="0 - HIDDEN, 1 - LOW, 2 - MEDIUM, 3 - HIGH")
    tech_tags: list[str] = Field(description="Стек технологий (Python, FastAPI и т.д.)")
    explanation: str = Field(description="Почему выбран такой приоритет?")
    confidence: float = Field(description="Уверенность в ответе от 0.0 до 1.0")


class GeminiAnalyzer:
    def __init__(self):
        self.key_manager = KeyProvider()
        self.api_key = self.key_manager.get_key()
        self.client = genai.Client(api_key=self.api_key)
        self.system_instruction = textwrap.dedent("""
            ОБЯЗАТЕЛЬНОЕ ПРАВИЛО: Всегда отвечай только на русском языке.

            Ты — профессиональный технический рекрутер, фильтрующий заказы строго для Python-разработчика.
            Твоя задача — найти проекты, где Python является необходимым или наиболее вероятным инструментом.

            КРИТЕРИИ ПРИОРИТЕТА:
            3 (HIGH): 
            - Прямое упоминание Python, Django, FastAPI, Flask, Aiogram, Selenium, Scrapy, Pandas.
            - Сложные Telegram-боты или парсеры (где Python — стандарт).
            - Backend-разработка сложных систем.

            2 (MEDIUM): 
            - Веб-разработка, где стек не указан, но описание подразумевает сложную логику (не просто "сайт-визитка").
            - Автоматизация данных, работа с API.

            1 (LOW): 
            - Общая веб-разработка (PHP, Laravel, Node.js, WordPress, Bitrix, Tilda).
            - Frontend задачи (React, Vue, верстка), если это не часть Python-проекта.
            - Настройка серверов (DevOps), если нет связи с кодом.

            0 (HIDDEN): 
            - Контент, дизайн, SMM, копирайтинг, Excel, ручной ввод данных, SEO.

            ВАЖНЫЕ ПРАВИЛА:
            1. НИКОГДА не добавляй тег "Python", если он не упомянут в тексте или если задача не является классической для Python (как парсер или сложный бот).
            2. Если в заказе упоминается другой стек (PHP, WordPress, 1C) — это приоритет 1 или 0.
            3. Одностраничники, лендинги и "сайты под ключ" без указания стека — это всегда приоритет 1.
        """).strip()
        self.limit = None

    def _swap_api_key(self):
        log.debug("swap key")
        self.api_key = self.key_manager.get_key()
        self.client = genai.Client(api_key=self.api_key)

    async def analyze_batch(self, jobs_to_analyze: list[JobView], batch_size: int = 15):

        chunks = [
            jobs_to_analyze[i: i + batch_size]
            for i in range(0, len(jobs_to_analyze), batch_size)
        ]

        chunks = chunks[:self.limit]

        for chunk in chunks:
            temp_jobs_map = {}
            batch_text_parts = []

            for index, jv in enumerate(chunk):
                temp_id = str(index)  # Это и есть наш идеальный короткий origin_id
                temp_jobs_map[temp_id] = jv

                # В текст для ИИ подставляем короткий номер, а не длинный URL
                batch_text_parts.append(
                    f"ID: {temp_id}\nЗаголовок: {jv.job.title}\nОписание: {jv.job.description}"
                )

            batch_text = "\n---\n".join(batch_text_parts)

            try:
                response = await self.client.aio.models.generate_content(
                    model="gemini-2.5-flash-lite",
                    contents=f"Проанализируй следующие заказы и верни массив JSON:\n{batch_text}",
                    config={
                        'system_instruction': self.system_instruction,
                        'response_mime_type': 'application/json',
                        'response_schema': list[GeminiSchema],
                    }
                )

                if not response.parsed:
                    log.warning("Нейросеть вернула пустой ответ или сработал фильтр! Пропускаем пачку.")
                    continue

                for ai_data in response.parsed:
                    # 2. Достаем объект обратно из словаря по короткому номеру
                    job_view = temp_jobs_map.get(ai_data.origin_id)

                    if job_view:
                        # Если заказ найден, обогащаем его данными от ИИ
                        final_pri = ai_data.priority_value if ai_data.is_relevant else 0
                        final_pri = max(0, min(final_pri, 3))

                        job_view.ai = AIAnalysis(
                            priority=JobPriority(final_pri),
                            explanation=ai_data.explanation,
                            tech_tags=ai_data.tech_tags,
                            confidence=ai_data.confidence
                        )
                    else:
                        log.warning(f"ИИ вернул несуществующий номер: {ai_data.origin_id}")
            except Exception as e:
                log.exception(f"Ошибка при обработке пачки: {e}")
                self._swap_api_key()

            await asyncio.sleep(2)