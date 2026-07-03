


import logging
from functools import wraps

from httpx import AsyncClient, ConnectError

log = logging.getLogger(__name__)


def handle_ext_api(func):
    @wraps(func)
    async def wrapper(self, *args, **kwargs):
        try:
            return await func(self, *args, **kwargs)
        except ConnectError:
            log.warning("поключение не установлено")

    return wrapper


def add_exception_handler(cls):
    api_methods = ["generate_image"]
    for attr_name in dir(cls):
        attr = getattr(cls, attr_name)
        if attr in api_methods:
            setattr(cls, attr_name, handle_ext_api(attr))
    return cls


class HttpClient:

    def __init__(self, url=None, app=None):
        self._url = url
        self._app = app
        self.headers = {
            "User-Agent": "Mozilla/5.0",
            "Accept": "application/rss+xml, application/xml, text/xml, */*",
            "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
        }
        self._client = AsyncClient(
            headers=self.headers,
            timeout=20,
        )

    @property
    def client(self):
        if self._client is None:
            raise RuntimeError("HTTP client is not initialized")
        return self._client

    async def fetch(self, url: str) -> str:
        resp = await self.client.get(url)
        resp.raise_for_status()
        return resp.text

    # async def fetch_fl_jobs(self, url: str) -> list[FreelanceJob]:
    #     resp = await self.client.get(url)
    #     resp.raise_for_status()
    #     xml_text = resp.text
    #     return parse_fl_rss(xml_text)

    async def close(self):
        if self._client:
            await self.client.aclose()
            self._client = None
