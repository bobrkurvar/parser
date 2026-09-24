from httpx import AsyncClient, HTTPStatusError

from hh.dto import VacancyPreview, VacancyDetails
import logging
from hh.config import conf
from scraper_engine import Factory, Scraper
from exceptions import RateLimitError, ResourceNotFoundError

log = logging.getLogger(__name__)


class HttpClient:
    BASE_URL = "https://api.hh.ru"
    _scraper = Scraper(retry_on=RateLimitError, decrease_on=RateLimitError, failed_on=ResourceNotFoundError)

    def __init__(self) -> None:
        headers = {
            "User-Agent": "hh_watcher/0.1 (andrey.bogdanov2005@mail.ru)",
            "Authorization": f"Bearer {conf.access_token}",
        }

        self._client = AsyncClient(
            base_url=self.BASE_URL,
            headers=headers,
            timeout=20.0,
        )

    async def close(self) -> None:
        await self._client.aclose()


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


    async def get_areas(self) -> list[dict]:
        response = await self._get("/areas")
        response.raise_for_status()
        return response.json()


    async def get_vacancies(self, previews: list[VacancyPreview], batch_size = 15):
        factories = [Factory(self.get_vacancies_by_query, preview.id) for preview in previews]
        return await self._scraper.execute_batch(factories=factories, batch_size=batch_size, static=False)


    async def get_vacancy(self, vacancy_id: int) -> VacancyDetails:
        response = await self._get(f"/vacancies/{vacancy_id}")
        if response.is_error:
            log.warning(
                "Ошибка получения вакансии %s: " "status=%s, body=%s",
                vacancy_id,
                response.status_code,
                response.text,
            )
        response.raise_for_status()
        return VacancyDetails.from_api(response.json())


    async def get_vacancies_by_queries(self, queries: list[str], batch_size = 15, **kwargs):
        factories = [Factory(self.get_vacancies_by_query, query, **kwargs) for query in queries]
        return await self._scraper.execute_batch(factories=factories, batch_size=batch_size, static=False)


    async def get_vacancies_by_query(
        self, query: str, **kwargs #area_id: int | None = None
    ) -> list[VacancyPreview]:
        vacancies: list[VacancyPreview] = []
        page = 0

        while True:
            params = {
                "text": query,
                "page": page,
                "per_page": 100,
            }
            params.update(**kwargs)

            # if area_id is not None:
            #     params["area"] = area_id

            response = await self._get("/vacancies", params=params)
            if response.is_error:
                log.warning(
                    "Ошибка HH API: status=%s, body=%s",
                    response.status_code,
                    response.text,
                )
            response.raise_for_status()

            payload = response.json()

            vacancies.extend(
                VacancyPreview.from_api(
                    item,
                    query=query,
                )
                for item in payload["items"]
            )

            if page + 1 >= payload["pages"]:
                break

            page += 1

        return vacancies
