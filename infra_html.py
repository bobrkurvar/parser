import re
from bs4 import BeautifulSoup
from dto import FlJobPage


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


def parse_first_int(text: str | None) -> int | None:
    if not text:
        return None

    match = re.search(r"\d[\d\s\u00a0]*", text)

    if match is None:
        return None

    return int(
        re.sub(r"[\s\u00a0]", "", match.group())
    )


def parse_price_range(text: str | None) -> tuple[int | None, int | None]:
    if not text:
        return None, None

    numbers = [
        int(re.sub(r"[\s\u00a0]", "", value))
        for value in re.findall(r"\d[\d\s\u00a0]*", text)
    ]

    if not numbers:
        return None, None

    if len(numbers) == 1:
        return numbers[0], numbers[0]

    return numbers[0], numbers[1]


def get_response_stats(soup: BeautifulSoup):
    stats_node = soup.select_one(
        "#proposal-hidden-block .proposals-content-block"
    )

    if stats_node is None:
        return None, None, None

    values: dict[str, str] = {}

    for row in stats_node.select(".mt-10"):
        label_node = row.select_one(".text-6")
        value_node = row.select_one(".text-5")

        if label_node is None or value_node is None:
            continue

        label = normalize_text(
            label_node.get_text(" ", strip=True)
        ).removesuffix(":")

        value = normalize_text(
            value_node.get_text(" ", strip=True)
        )

        values[label] = value

    responses_count = parse_first_int(values.get("Откликнулись"))
    min_price, max_price = parse_price_range(values.get("Цены"))

    return responses_count, min_price, max_price



def parse_fl_job_page(html: str) -> FlJobPage:
    soup = BeautifulSoup(html, "lxml")

    responses_count, response_price_min, response_price_max = (
        get_response_stats(soup)
    )

    return FlJobPage(
        description=get_description(soup),
        budget_text=get_budget_text(soup),
        responses_count=responses_count,
        response_price_min=response_price_min,
        response_price_max=response_price_max,
    )