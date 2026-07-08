from dto import FreelanceJob
from keywords import CONTENT_KEYWORDS, EXCLUDED_TERMS
import re
import logging

log = logging.getLogger(__name__)


def normalize_text(text: str) -> str:
    text = text.lower()
    text = text.replace("ё", "е")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def has_cyrillic(text: str) -> bool:
    return bool(re.search(r"[а-яё]", text))


def make_pattern(term: str) -> re.Pattern:
    term = normalize_text(term)
    words = term.split()

    pattern = r"\s+".join(
        rf"{re.escape(word)}\w*"
        if has_cyrillic(word)
        else re.escape(word)
        for word in words
    )

    return re.compile(
        rf"(?<!\w){pattern}(?!\w)",
        re.IGNORECASE,
    )


CONTENT_PATTERNS = {
    term: make_pattern(term)
    for term in CONTENT_KEYWORDS
}

EXCLUDED_PATTERNS = {
    term: make_pattern(term)
    for term in EXCLUDED_TERMS
}

def find_matches(terms_patterns: dict[str, re.Pattern], *parts: str) -> list[str]:
    text = normalize_text(" ".join(parts))

    return [
        term
        for term, pattern in terms_patterns.items()
        if pattern.search(text)
    ]


def find_content_keywords(*parts: str) -> list[str]:
    return find_matches(CONTENT_PATTERNS, *parts)


def find_excluded_stack(*parts: str) -> list[str]:
    return find_matches(EXCLUDED_PATTERNS, *parts)



def analyze_basic(job: FreelanceJob) -> bool:
    content = find_content_keywords(job.title, job.description)
    excluded = find_excluded_stack(job.title, job.description)

    if not content and excluded:
        return False

    return True

