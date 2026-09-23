from .yandex import YandexAIProvider

from fl.dto import AIAnalysis, JobPriority
from exceptions import RateLimitError
from fl.literals import SYSTEM_INSTRUCTION, TARGET_TECHNOLOGIES
import logging
import textwrap
from scraper_engine import Scraper, Factory

log = logging.getLogger(__name__)


class InvalidAIResponse(Exception):
    pass



class AIAnalyzer:
    _scraper = Scraper(
        retry_on=(InvalidAIResponse, RateLimitError),
        max_retries=None
    )

    def __init__(self, ai_provider):
        self.provider = ai_provider

        target_technologies = ", ".join(TARGET_TECHNOLOGIES)

        self.system_instruction = textwrap.dedent(
            SYSTEM_INSTRUCTION.format(
                target_technologies=target_technologies
            )
        ).strip()

        self.limit = None

    @staticmethod
    def _build_batch_text(chunk: list[tuple[str, str]]) -> str:
        batch_text_parts = []

        for index, (title, description) in enumerate(chunk):
            batch_text_parts.append(
                f"ID: {index}\n"
                f"Заголовок: {title}\n"
                f"Описание: {description}"
            )

        return "\n---\n".join(batch_text_parts)


    def _build_result(self):



    async def _process_single_chunk(
        self,
        chunk: list[tuple[str, str]],
        start_index: int,
    ) -> list[tuple[int, AIAnalysis]]:
        # анализ выходных данные из провайдера, должен быть batch index
        batch_text = self._build_batch_text(chunk)
        ai_results = await self.provider.analyze(
            system_instruction=self.system_instruction,
            batch_text=batch_text,
        )
        if not all("batch_index" in res for res in ai_results):
            raise ValueError("В ответе нет индекса пачки")

        parsed_results = []
        for ai_data in ai_results:
            if not 0 <= ai_data.batch_index < len(chunk):
                raise InvalidAIResponse(
                    f"Несуществующий batch_index: "
                    f"{ai_data.batch_index}"
                )

            priority_value = max(
                JobPriority.HIDDEN,
                min(
                    ai_data.priority_value,
                    JobPriority.HIGH,
                ),
            )

            analysis_obj = AIAnalysis(
                priority=JobPriority(priority_value),
                explanation=ai_data.explanation,
                confidence=ai_data.confidence,
            )

            absolute_index = start_index + ai_data.batch_index
            parsed_results.append((absolute_index, analysis_obj))

        return parsed_results

    async def analyze_jobs(
        self,
        jobs_to_analyze: list[tuple[str, str]],
        batch_size: int = 15,
    ) -> list[AIAnalysis | None]:
        if not jobs_to_analyze:
            return []

        result: list[AIAnalysis | None] = [None] * len(jobs_to_analyze)
        factories = []

        for chunk_number, start_index in enumerate(range(0, len(jobs_to_analyze), batch_size)):
            if self.limit is not None and chunk_number >= self.limit:
                break

            chunk = jobs_to_analyze[start_index:start_index + batch_size]

            factories.append(
                Factory(
                    self._process_single_chunk,
                    chunk,
                    start_index,
                    context=start_index
                )
            )
        results, failed = await self._scraper.execute_batch(factories=factories, batch_size=3)

        for _, chunk_result in results:
            for absolute_index, analysis_obj in chunk_result:
                result[absolute_index] = analysis_obj

        for start_index, exc in failed:
            log.error(
                "Не удалось обработать пачку с start_index=%s: %s",
                start_index,
                exc,
            )

        return result

