from __future__ import annotations

from typing import Any

import httpx


class ServerClient:
    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.client = httpx.Client(base_url=self.base_url, timeout=10.0)

    def get(self, path: str) -> Any:
        response = self.client.get(path)
        response.raise_for_status()
        return response.json()

    def post(self, path: str, payload: dict[str, Any] | None = None) -> Any:
        response = self.client.post(path, json=payload or {})
        response.raise_for_status()
        return response.json() if response.content else None

    def delete(self, path: str, params: dict[str, Any] | None = None) -> None:
        response = self.client.delete(path, params=params)
        response.raise_for_status()

    def close(self) -> None:
        self.client.close()

