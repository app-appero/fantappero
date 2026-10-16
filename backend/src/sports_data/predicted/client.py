"""Client HTTP di FotMob via RapidAPI.

La chiave resta nell'header e non entra in log, eccezioni o URL.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

import httpx

from config.settings.redaction import redact_secrets

_HOST = "fotmob-api.p.rapidapi.com"


class FotmobError(Exception):
    def __init__(self, status: int | None, message: str) -> None:
        super().__init__(redact_secrets(message))
        self.status = status


class FotmobClient:
    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = f"https://{_HOST}",
        timeout_seconds: float = 20.0,
        max_retries: int = 2,
        min_interval_seconds: float = 0.25,
        transport: httpx.BaseTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._api_key = api_key
        self._max_retries = max_retries
        self._min_interval = min_interval_seconds
        self._sleep = sleep
        self._cache: dict[str, Any] = {}
        self.requests_made = 0
        self._http = httpx.Client(
            base_url=base_url.rstrip("/"),
            timeout=timeout_seconds,
            transport=transport,
            headers={
                "x-rapidapi-host": _HOST,
                "x-rapidapi-key": api_key,
                "accept": "application/json",
            },
        )

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> FotmobClient:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def matches_by_date(self, date_yyyymmdd: str) -> Any:
        return self._get_json("/api/v1/matches/by-date", params={"date": date_yyyymmdd})

    def lineups(self, match_id: int) -> Any:
        return self._get_json(f"/api/v1/matches/{match_id}/lineups")

    def _get_json(self, path: str, params: dict[str, str] | None = None) -> Any:
        query = "&".join(f"{key}={value}" for key, value in sorted((params or {}).items()))
        cache_key = f"{path}?{query}"
        if cache_key in self._cache:
            return self._cache[cache_key]
        payload = self._request(path, params)
        self._cache[cache_key] = payload
        return payload

    def _request(self, path: str, params: dict[str, str] | None) -> Any:
        attempt = 0
        while True:
            if self.requests_made:
                self._sleep(self._min_interval)
            try:
                response = self._http.get(path, params=params)
            except httpx.TimeoutException as exc:
                if attempt >= self._max_retries:
                    raise FotmobError(
                        None,
                        "Timeout verso il provider delle formazioni probabili.",
                    ) from exc
                self._sleep(self._backoff(attempt))
                attempt += 1
                continue
            except httpx.HTTPError as exc:
                if attempt >= self._max_retries:
                    raise FotmobError(
                        None,
                        "Errore di rete verso il provider delle formazioni probabili.",
                    ) from exc
                self._sleep(self._backoff(attempt))
                attempt += 1
                continue
            self.requests_made += 1
            status = response.status_code
            if status == 200:
                try:
                    return response.json()
                except ValueError as exc:
                    raise FotmobError(status, "Risposta del provider non in JSON.") from exc
            if status in {401, 403}:
                raise FotmobError(
                    status,
                    f"Provider formazioni probabili: accesso rifiutato ({status}).",
                )
            if status == 404:
                raise FotmobError(status, "Formazione o giornata non trovata sul provider.")
            if status == 429 or status >= 500:
                if attempt >= self._max_retries:
                    raise FotmobError(
                        status,
                        f"Provider formazioni probabili non disponibile ({status}).",
                    )
                delay = self._retry_after(response) if status == 429 else self._backoff(attempt)
                self._sleep(delay)
                attempt += 1
                continue
            raise FotmobError(status, f"Provider formazioni probabili: risposta {status}.")

    @staticmethod
    def _backoff(attempt: int) -> float:
        return min(8.0, 0.5 * (2**attempt))

    @staticmethod
    def _retry_after(response: httpx.Response) -> float:
        raw = response.headers.get("retry-after") or response.headers.get("Retry-After")
        if raw and raw.isdigit():
            return min(30.0, float(raw))
        return 2.0
