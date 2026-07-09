import xml.etree.ElementTree as ET
from dto import FeedJob
from html import unescape
import re
import logging

log = logging.getLogger(__name__)

def clean_html(text: str) -> str:
    text = unescape(text or "")
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()

PROJECT_ID_PATTERN = re.compile(r"/projects/(\d+)/")


def extract_fl_project_id(url: str) -> int | None:
    match = PROJECT_ID_PATTERN.search(url)
    return int(match.group(1)) if match else None


def parse_fl_rss(
    xml_text: str,
    feed_name: str,
) -> list[FeedJob]:
    root = ET.fromstring(xml_text)

    jobs: list[FeedJob] = []

    for item in root.findall(".//item"):
        title = clean_html(item.findtext("title", default=""))
        description = clean_html(
            item.findtext("description", default="")
        )
        link = item.findtext("link", default="").strip()
        pub_date = item.findtext("pubDate", default="").strip()

        external_id = extract_fl_project_id(link)

        if external_id is None:
            log.warning(
                "Не удалось извлечь ID проекта из URL: %s",
                link,
            )
            continue

        categories = [
            clean_html(category.text or "")
            for category in item.findall("category")
        ]

        jobs.append(
            FeedJob(
                source="fl.ru",
                external_id=external_id,
                title=title,
                url=link,
                tags=categories,
                published_at=pub_date or None,
                feed_name=feed_name,
            )
        )

    log.debug("Всего заказов: %d", len(jobs))
    return jobs