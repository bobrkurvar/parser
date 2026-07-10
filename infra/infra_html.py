from bs4 import BeautifulSoup
from dto import JobPageData, OfferRange
import logging
import base64
import json


log = logging.getLogger(__name__)


def normalize_text(text: str) -> str:
    return " ".join(text.split())


def get_description(soup: BeautifulSoup) -> str:
    node = soup.select_one(".fl-project-content__description-text")

    if node is None:
        raise ValueError("Не найдено описание заказа")

    lines = [
        line.strip()
        for line in node.get_text("\n").splitlines()
        if line.strip()
    ]

    return "\n".join(lines)


def get_budget_text(soup: BeautifulSoup) -> str | None:
    for node in soup.select("div.text-4"):
        text = normalize_text(node.get_text(" ", strip=True))

        if not text.startswith("Бюджет:"):
            continue

        value_node = node.find("span")

        if value_node is not None:
            return normalize_text(value_node.get_text(" ", strip=True))

        budget = text.removeprefix("Бюджет:").strip()
        return budget or None

    return None


def get_is_closed(soup: BeautifulSoup) -> bool:
    status_block = soup.select_one(
        '[id^="project_status_"]',
    )

    if status_block is None:
        return False

    status_text = normalize_text(
        status_block.get_text(" ", strip=True),
    )

    return "Заказчик выбрал исполнителя" in status_text


def parse_fl_job_page(html: str) -> JobPageData:
    soup = BeautifulSoup(html, "lxml")
    result = JobPageData(
        description=get_description(soup),
        budget_text=get_budget_text(soup),
        is_closed=get_is_closed(soup),
    )
    #log.debug("Парсинг завершён: %s", result)
    return result


def offer_range(response_data: dict) -> OfferRange:
    encoded_result = response_data.get("result")
    if not encoded_result:
        raise ValueError("Тело offer range не удалось декодировать")

    token = base64.b64decode(encoded_result,).decode("utf-8")
    _, payload_part, _ = token.split(".", maxsplit=2)
    payload_part += "=" * (-len(payload_part) % 4)
    payload = json.loads(base64.urlsafe_b64decode(payload_part))

    return OfferRange(
        responses_count=payload.get("freelancersCount"),
        response_price_min=payload.get("minCost"),
        response_price_max=payload.get("maxCost")
    )