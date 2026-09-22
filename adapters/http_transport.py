import httpx


class HttpTransport:
    def __init__(
        self,
        *,
        base_url: str | None = None,
        headers: dict | None = None,
        timeout: float = 20,
    ):
        self._client = httpx.AsyncClient(
            base_url=base_url or "",
            headers=headers,
            timeout=timeout,
        )

    @property
    def client(self):
        if self._client is None:
            raise RuntimeError("HTTP client is not initialized")
        return self._client

    async def get(self, url, **kwargs):
        response = await self._client.get(url, **kwargs)
        response.raise_for_status()
        return response


    async def close(self):
        await self._client.aclose()