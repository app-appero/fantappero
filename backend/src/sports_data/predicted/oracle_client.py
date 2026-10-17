"""Client HTTP del motore identità giocatori di Soccer-Oracle (romy1992/ia_predict_soccer).

La chiave resta nell'header e non entra in log, eccezioni o URL — stesso
trattamento del client FotMob in ``client.py``.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

import httpx

from config.settings.redaction import redact_secrets


class SoccerOracleError(Exception):
    def __init__(self, status: int | None, message: str) -> None:
        super().__init__(redact_secrets(message))
        self.status = status


class SoccerOracleClient:
    def __init__(
        self,
        api_key: str,
        *,
        base_url: str,
        timeout_seconds: float = 5.0,
        max_retries: int = 1,
        transport: httpx.BaseTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._max_retries = max_retries
        self._sleep = sleep
        self.requests_made = 0
        self._http = httpx.Client(
            base_url=base_url.rstrip("/"),
            timeout=timeout_seconds,
            transport=transport,
            headers={"X-Service-Key": api_key, "accept": "application/json"},
        )

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> SoccerOracleClient:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def lineups(self, fixture_ids: list[int], *, prefer: str = "predicted") -> Any:
        if not fixture_ids:
            return {"count": 0, "fixtures": []}
        if len(fixture_ids) > 50:
            raise SoccerOracleError(None, "Troppi fixture_id in una sola chiamata (max 50).")
        ids = ",".join(str(value) for value in fixture_ids)
        return self._request(
            "GET", "/players/lineups", params={"fixture_ids": ids, "prefer": prefer}
        )

    def lookup(self, *, provider: str, provider_id: int) -> Any:
        """Ricerca per ID esatto del provider — niente ambiguità di nome."""
        return self._request(
            "GET",
            "/players/lookup",
            params={"provider": provider, "provider_id": str(provider_id)},
        )

    def links_bulk(self, links: list[dict[str, Any]], *, source: str = "external_project") -> Any:
        if not links:
            return {"count": 0}
        if len(links) > 500:
            raise SoccerOracleError(None, "Troppi collegamenti in una sola chiamata (max 500).")
        return self._request(
            "POST", "/players/links/bulk", json_body={"links": links, "source": source}
        )

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, str] | None = None,
        json_body: dict[str, Any] | None = None,
    ) -> Any:
        attempt = 0
        while True:
            try:
                response = self._http.request(method, path, params=params, json=json_body)
            except httpx.TimeoutException as exc:
                if attempt >= self._max_retries:
                    raise SoccerOracleError(
                        None, "Timeout verso il motore identità giocatori."
                    ) from exc
                self._sleep(self._backoff(attempt))
                attempt += 1
                continue
            except httpx.HTTPError as exc:
                if attempt >= self._max_retries:
                    raise SoccerOracleError(
                        None, "Errore di rete verso il motore identità giocatori."
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
                    raise SoccerOracleError(status, "Risposta non in JSON.") from exc
            if status in {401, 403}:
                raise SoccerOracleError(
                    status, f"Motore identità giocatori: accesso rifiutato ({status})."
                )
            if status == 404:
                raise SoccerOracleError(
                    status, "Risorsa non trovata sul motore identità giocatori."
                )
            if status == 429 or status >= 500:
                if attempt >= self._max_retries:
                    raise SoccerOracleError(
                        status, f"Motore identità giocatori non disponibile ({status})."
                    )
                delay = self._retry_after(response) if status == 429 else self._backoff(attempt)
                self._sleep(delay)
                attempt += 1
                continue
            raise SoccerOracleError(status, f"Motore identità giocatori: risposta {status}.")

    @staticmethod
    def _backoff(attempt: int) -> float:
        return min(4.0, 0.5 * (2**attempt))

    @staticmethod
    def _retry_after(response: httpx.Response) -> float:
        raw = response.headers.get("retry-after") or response.headers.get("Retry-After")
        if raw and raw.isdigit():
            return min(15.0, float(raw))
        return 1.0
