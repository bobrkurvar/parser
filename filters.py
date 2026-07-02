from dto import FreelanceJob
from keywords import CONTENT_KEYWORDS, EXCLUDED_STACK_PATTERNS
import re
import logging
from dto import JobPriority

log = logging.getLogger(__name__)


def normalize_text(text: str) -> str:
    text = text.lower()
    text = text.replace("ё", "е")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


NORMALIZED_CONTENT_KEYWORDS = {
    normalize_text(keyword)
    for keyword in CONTENT_KEYWORDS
}


def find_content_keywords(*parts: str) -> list[str]:
    return [
        keyword
        for keyword in NORMALIZED_CONTENT_KEYWORDS
        if keyword in normalize_text(" ".join(parts))
    ]

def find_excluded_stack(*parts: str) -> dict[str, list[str]]:
    text = normalize_text(" ".join(parts))

    result = {}

    for stack_name, patterns in EXCLUDED_STACK_PATTERNS.items():
        matched_patterns = []

        for pattern in patterns:
            if re.search(pattern, text, flags=re.IGNORECASE):
                matched_patterns.append(pattern)

        if matched_patterns:
            result[stack_name] = matched_patterns

    return result


def analyze_basic(job: FreelanceJob) -> bool:
    content = find_content_keywords(
        job.title,
        job.description,
    )
    excluded_stack = find_excluded_stack(
        job.title,
        job.description,
    )

    if not content and excluded_stack:
        return False

    return True

# def analyze_basic(job: FreelanceJob) -> BasicAnalysis:
#     content = find_content_keywords(job.title, job.description)
#     excluded_stack = find_excluded_stack(job.title, job.description)
#     priority, content_keywords, stack, reason = JobPriority.MEDIUM, [], {}, "Нет явных полезных слов, но категория подходит"
#     if content and not excluded_stack:
#         priority, content_keywords, stack, reason = JobPriority.HIGH, content, {}, "Есть полезные ключевые слова"
#     elif content and excluded_stack:
#         priority, content_keywords, stack, reason= JobPriority.LOW, content, excluded_stack, "Есть полезные слова, но найден чужой стек"
#     elif not content and excluded_stack:
#         priority, content_keywords, stack, reason = JobPriority.HIDDEN, [], excluded_stack, "Чужой стек без полезных сигналов"
#
#     return BasicAnalysis(
#         priority=priority,
#         content_keywords=content_keywords,
#         excluded_stack=stack,
#         reason=reason,
#     )
