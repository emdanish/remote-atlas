from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

import httpx

from app.pipeline.normalize import NormalizedJob

DEFAULT_HEADERS = {
    "User-Agent": "RemoteAtlas/0.1 (+https://github.com/emdanish/remote-atlas; personal job discovery)",
    "Accept": "application/json",
}


class BaseCollector(ABC):
    source: str

    def __init__(self, client: Optional[httpx.AsyncClient] = None):
        self._client = client
        self._owns_client = client is None

    async def __aenter__(self) -> "BaseCollector":
        if self._client is None:
            self._client = httpx.AsyncClient(headers=DEFAULT_HEADERS, timeout=60.0, follow_redirects=True)
        return self

    async def __aexit__(self, *args) -> None:
        if self._owns_client and self._client is not None:
            await self._client.aclose()

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            raise RuntimeError("Collector client not initialized; use async with")
        return self._client

    @abstractmethod
    async def fetch(self) -> list[NormalizedJob]:
        raise NotImplementedError
