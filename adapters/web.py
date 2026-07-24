import logging
from functools import wraps
from exceptions import RateLimitError, ResourceNotFoundError
from httpx import AsyncClient, ConnectError, HTTPStatusError

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
    BASE_URL = "https://www.fl.ru"

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

    async def _get(
        self,
        url: str,
        *,
        params: dict | None = None,
        headers: dict | None = None,
    ):
        try:
            response = await self._client.get(
                url,
                params=params,
                headers=headers,
            )
            response.raise_for_status()
            return response

        except HTTPStatusError as exc:
            status_code = exc.response.status_code

            if status_code == 404:
                raise ResourceNotFoundError(f"Ресурс не найден: {url}") from exc

            if status_code == 429:
                raise RateLimitError(f"Rate limit: {url}") from exc


    async def fetch_rss(
        self,
        category_id: int,
        subcategory_id: int,
    ) -> str:
        url = f"{self.BASE_URL}/rss/all.xml"
        return (await self._get(
            url,
            params={
                "category": category_id,
                "subcategory": subcategory_id,
            }
        )).text


    async def fetch_project_page(self, project_url: str) -> str:
        return (await self._get(project_url)).text


    async def fetch_offer_range(self, project_id: int) -> dict:
        url = f"{self.BASE_URL}/projects/{project_id}/offers/range/"

        return (await self._get(
            url,
            headers={}
        )).json()



    async def close(self):
        if self._client:
            await self.client.aclose()
            self._client = None
