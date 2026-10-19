"""Client HTTP per l'Expo Push API (invio notifiche push ai dispositivi mobile)."""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

import httpx

_MAX_MESSAGES_PER_REQUEST = 100


class ExpoPushError(Exception):
    def __init__(self, status: int | None, message: str) -> None:
        super().__init__(message)
        self.status = status


class ExpoPushClient:
    def __init__(
        self,
        *,
        base_url: str = "https://exp.host/--/api/v2/push/send",
        access_token: str | None = None,
        timeout_seconds: float = 10.0,
        max_retries: int = 1,
        transport: httpx.BaseTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._url = base_url
        self._max_retries = max_retries
        self._sleep = sleep
        headers = {"accept": "application/json", "content-type": "application/json"}
        if access_token:
            headers["authorization"] = f"Bearer {access_token}"
        self._http = httpx.Client(timeout=timeout_seconds, transport=transport, headers=headers)

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> ExpoPushClient:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def send(self, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Manda fino a 100 messaggi per chiamata, ticket Expo nello stesso ordine dei messaggi."""
        if not messages:
            return []
        results: list[dict[str, Any]] = []
        for start in range(0, len(messages), _MAX_MESSAGES_PER_REQUEST):
            batch = messages[start : start + _MAX_MESSAGES_PER_REQUEST]
            results.extend(self._post(batch))
        return results

    def _post(self, batch: list[dict[str, Any]]) -> list[dict[str, Any]]:
        attempt = 0
        while True:
            try:
                response = self._http.post(self._url, json=batch)
            except httpx.TimeoutException as exc:
                if attempt >= self._max_retries:
                    raise ExpoPushError(None, "Timeout verso Expo Push API.") from exc
                self._sleep(self._backoff(attempt))
                attempt += 1
                continue
            except httpx.HTTPError as exc:
                if attempt >= self._max_retries:
                    raise ExpoPushError(None, "Errore di rete verso Expo Push API.") from exc
                self._sleep(self._backoff(attempt))
                attempt += 1
                continue
            status = response.status_code
            if status == 200:
                try:
                    payload = response.json()
                except ValueError as exc:
                    raise ExpoPushError(status, "Risposta Expo non in JSON.") from exc
                data = payload.get("data") if isinstance(payload, dict) else None
                return data if isinstance(data, list) else []
            if status == 429 or status >= 500:
                if attempt >= self._max_retries:
                    raise ExpoPushError(status, f"Expo Push API non disponibile ({status}).")
                self._sleep(self._backoff(attempt))
                attempt += 1
                continue
            raise ExpoPushError(status, f"Expo Push API: risposta {status}.")

    @staticmethod
    def _backoff(attempt: int) -> float:
        return min(4.0, 0.5 * (2**attempt))
