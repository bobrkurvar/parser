import logging
from exceptions import RateLimitError, ResourceNotFoundError
from httpx import AsyncClient, ConnectError, HTTPStatusError
from dto import FeedJob, JobStaticData
from scraper_engine import Scraper, Factory

log = logging.getLogger(__name__)


class HttpClient:
    BASE_URL = "https://www.fl.ru"
    _scraper = Scraper(retry_on=RateLimitError, decrease_on=RateLimitError, failed_on=ResourceNotFoundError)

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

            raise

    @staticmethod
    def _get_job_url(job: JobStaticData | FeedJob) -> str:
        return job.feed_job.url if isinstance(job, JobStaticData) else job.url


    async def fetch_project_page(self, project_url: str) -> str:
        return (await self._get(project_url)).text


    async def fetch_pages(self, jobs: list[JobStaticData | FeedJob], batch_size: int = 20, static: bool = False):
        factories = [Factory(self.fetch_project_page, self._get_job_url(job), context=job) for job in jobs]
        return await self._scraper.execute_batch(factories=factories, batch_size=batch_size, static=static)


    async def fetch_offer_range(self, project_id: int) -> dict:
        url = f"{self.BASE_URL}/projects/{project_id}/offers/range/"

        return (await self._get(
            url,
            headers={}
        )).json()


    async def fetch_offer_data(self, jobs: list[JobStaticData], batch_size: int = 20, static: bool = False):
        factories = [Factory(self.fetch_offer_range, job.feed_job.external_id, context=job) for job in jobs]
        return await self._scraper.execute_batch(factories=factories, batch_size=batch_size, static=static)


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




    async def close(self):
        if self._client:
            await self.client.aclose()
            self._client = None
