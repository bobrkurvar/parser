import xml.etree.ElementTree as ET
from dto import FreelanceJob
from html import unescape
import re
import logging

log = logging.getLogger(__name__)

def clean_html(text: str) -> str:
    text = unescape(text or "")
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def parse_fl_rss(xml_text: str) -> list[FreelanceJob]:
    root = ET.fromstring(xml_text)

    jobs: list[FreelanceJob] = []

    for item in root.findall(".//item"):
        title = clean_html(item.findtext("title", default=""))
        description = clean_html(item.findtext("description", default=""))
        link = item.findtext("link", default="").strip()
        guid = item.findtext("guid", default="").strip()
        pub_date = item.findtext("pubDate", default="").strip()

        categories = [
            clean_html(category.text or "")
            for category in item.findall("category")
        ]

        jobs.append(
            FreelanceJob(
                source="fl.ru",
                external_id=guid or link,
                title=title,
                description=description,
                url=link,
                tags=categories,
                published_at=pub_date or None,
            )
        )
    log.debug(f"Всего заказов: {len(jobs)}")
    return jobs
