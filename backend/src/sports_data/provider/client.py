"""HTTP client for API-Football v3 — sole network boundary (ADR-0001 / EP04-01)."""

from __future__ import annotations

import time
from collections.abc import Mapping
from typing import Any

import httpx

from observability.logging import get_logger
from observability.metrics import Timer, get_metrics
from sports_data.provider.constants import AUTH_HEADER, DEFAULT_BASE_URL, PROVIDER_NAME
from sports_data.provider.envelope import (
    errors_indicate_rate_limit,
    merge_envelopes,
    parse_envelope,
    parse_rate_limit_headers,
)
from sports_data.provider.errors import (
    ProviderAuthError,
    ProviderConfigError,
    ProviderHttpError,
    ProviderRateLimitError,
    ProviderResponseError,
)
from sports_data.provider.throttle import (
    DEFAULT_RATE_LIMIT_PAUSE_SECONDS,
    DEFAULT_REQUESTS_PER_MINUTE,
    PROVIDER_THROTTLE_WAIT_SECONDS,
    PROVIDER_THROTTLE_WAITS_TOTAL,
    MinuteRateLimiter,
)
from sports_data.provider.types import ProviderEnvelope

logger = get_logger(__name__)

# Metric names (stable for tests / future exporters).
PROVIDER_REQUESTS_TOTAL = "provider_requests_total"
PROVIDER_REQUEST_ERRORS_TOTAL = "provider_request_errors_total"
PROVIDER_REQUEST_DURATION_SECONDS = "provider_request_duration_seconds"
PROVIDER_RETRIES_TOTAL = "provider_retries_total"
PROVIDER_RATE_LIMIT_REMAINING = "provider_rate_limit_remaining"
PROVIDER_RATE_LIMIT_PAUSES_TOTAL = "provider_rate_limit_pauses_total"


def normalize_path(path: str) -> str:
    text = path.strip()
    if not text.startswith("/"):
        text = f"/{text}"
    return text.rstrip("/") or "/"


class ApiFootballClient:
    """Centralised API-Football client: auth, pagination, retries, throttle, metrics.

    Clients (web/mobile) must never instantiate this with a browser-exposed key.
    """

    def __init__(
        self,
        *,
        api_key: str | None,
        base_url: str = DEFAULT_BASE_URL,
        timeout_seconds: float = 30.0,
        max_retries: int = 3,
        retry_backoff_seconds: float = 1.0,
        requests_per_minute: int = DEFAULT_REQUESTS_PER_MINUTE,
        rate_limit_pause_seconds: float = DEFAULT_RATE_LIMIT_PAUSE_SECONDS,
        max_rate_limit_pauses: int = 100,
        transport: httpx.BaseTransport | None = None,
        client: httpx.Client | None = None,
        rate_limiter: MinuteRateLimiter | None = None,
    ) -> None:
        if not api_key or not str(api_key).strip():
            raise ProviderConfigError(
                "Chiave provider assente: impostare API_FOOTBALL_KEY (solo backend)",
            )
        self._api_key = str(api_key).strip()
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout_seconds
        self._max_retries = max(0, max_retries)
        self._retry_backoff = max(0.0, retry_backoff_seconds)
        self._rate_limit_pause = max(1.0, float(rate_limit_pause_seconds))
        self._max_rate_limit_pauses = max(1, int(max_rate_limit_pauses))
        self._rate_limiter = rate_limiter or MinuteRateLimiter(
            max_per_minute=max(1, int(requests_per_minute)),
        )
        self._owns_client = client is None
        self._client = client or httpx.Client(
            base_url=self._base_url,
            timeout=httpx.Timeout(timeout_seconds),
            transport=transport,
            headers={AUTH_HEADER: self._api_key},
        )

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> ApiFootballClient:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def get(
        self,
        path: str,
        params: Mapping[str, Any] | None = None,
        *,
        fetch_all_pages: bool = True,
    ) -> ProviderEnvelope:
        """GET one endpoint; optionally walk ``paging.current..total``."""
        endpoint = normalize_path(path)
        base_params = {str(k): v for k, v in (params or {}).items() if v is not None}
        first = self._get_page(endpoint, base_params)
        if not fetch_all_pages or first.paging.total <= 1:
            return first

        pages = [first]
        for page_num in range(2, first.paging.total + 1):
            page_params = {**base_params, "page": page_num}
            pages.append(self._get_page(endpoint, page_params))
        return merge_envelopes(pages)

    def _get_page(self, endpoint: str, params: dict[str, Any]) -> ProviderEnvelope:
        metrics = get_metrics()
        labels = {"provider": PROVIDER_NAME, "endpoint": endpoint}
        attempt = 0
        rate_limit_pauses = 0
        while True:
            attempt += 1
            waited = self._rate_limiter.acquire()
            if waited > 0:
                metrics.incr(PROVIDER_THROTTLE_WAITS_TOTAL, labels={"provider": PROVIDER_NAME})
                metrics.observe(
                    PROVIDER_THROTTLE_WAIT_SECONDS,
                    waited,
                    labels={"provider": PROVIDER_NAME},
                )
            try:
                with Timer(metrics, PROVIDER_REQUEST_DURATION_SECONDS, labels=labels):
                    response = self._client.get(endpoint, params=params)
            except httpx.TimeoutException as exc:
                metrics.incr(
                    PROVIDER_REQUEST_ERRORS_TOTAL,
                    labels={**labels, "error_type": "timeout"},
                )
                if attempt <= self._max_retries:
                    self._sleep_backoff(attempt)
                    metrics.incr(PROVIDER_RETRIES_TOTAL, labels=labels)
                    continue
                raise ProviderHttpError(
                    "Timeout verso il provider sportivo",
                    endpoint=endpoint,
                ) from exc
            except httpx.TransportError as exc:
                metrics.incr(
                    PROVIDER_REQUEST_ERRORS_TOTAL,
                    labels={**labels, "error_type": "transport"},
                )
                if attempt <= self._max_retries:
                    self._sleep_backoff(attempt)
                    metrics.incr(PROVIDER_RETRIES_TOTAL, labels=labels)
                    continue
                raise ProviderHttpError(
                    "Errore di trasporto verso il provider sportivo",
                    endpoint=endpoint,
                ) from exc

            status = response.status_code
            rate_limit = parse_rate_limit_headers(response.headers)
            if rate_limit.remaining is not None:
                metrics.set_gauge(
                    PROVIDER_RATE_LIMIT_REMAINING,
                    float(rate_limit.remaining),
                    labels={"provider": PROVIDER_NAME},
                )

            if status == 401 or status == 403:
                metrics.incr(PROVIDER_REQUESTS_TOTAL, labels={**labels, "status": str(status)})
                metrics.incr(
                    PROVIDER_REQUEST_ERRORS_TOTAL,
                    labels={**labels, "error_type": "auth"},
                )
                logger.warning(
                    "provider_auth_rejected",
                    extra={"endpoint": endpoint, "status": status, "provider": PROVIDER_NAME},
                )
                raise ProviderAuthError(
                    "Autenticazione provider rifiutata",
                    endpoint=endpoint,
                )

            if status == 429:
                metrics.incr(PROVIDER_REQUESTS_TOTAL, labels={**labels, "status": "429"})
                metrics.incr(
                    PROVIDER_REQUEST_ERRORS_TOTAL,
                    labels={**labels, "error_type": "rate_limit"},
                )
                retry_after = _parse_retry_after(response.headers)
                if self._pause_for_rate_limit(
                    endpoint=endpoint,
                    pause_count=rate_limit_pauses,
                    override=retry_after,
                    metrics=metrics,
                    labels=labels,
                ):
                    rate_limit_pauses += 1
                    continue
                raise ProviderRateLimitError(
                    "Rate limit provider esaurito dopo pause ripetute",
                    endpoint=endpoint,
                    retry_after_seconds=retry_after,
                    remaining=rate_limit.remaining,
                )

            if status >= 500:
                metrics.incr(PROVIDER_REQUESTS_TOTAL, labels={**labels, "status": str(status)})
                metrics.incr(
                    PROVIDER_REQUEST_ERRORS_TOTAL,
                    labels={**labels, "error_type": "server"},
                )
                if attempt <= self._max_retries:
                    self._sleep_backoff(attempt)
                    metrics.incr(PROVIDER_RETRIES_TOTAL, labels=labels)
                    continue
                raise ProviderHttpError(
                    "Errore server del provider sportivo",
                    endpoint=endpoint,
                    status_code=status,
                )

            if status >= 400:
                metrics.incr(PROVIDER_REQUESTS_TOTAL, labels={**labels, "status": str(status)})
                metrics.incr(
                    PROVIDER_REQUEST_ERRORS_TOTAL,
                    labels={**labels, "error_type": "client"},
                )
                raise ProviderHttpError(
                    "Richiesta provider rifiutata",
                    endpoint=endpoint,
                    status_code=status,
                )

            metrics.incr(PROVIDER_REQUESTS_TOTAL, labels={**labels, "status": str(status)})
            try:
                payload = response.json()
            except ValueError as exc:
                metrics.incr(
                    PROVIDER_REQUEST_ERRORS_TOTAL,
                    labels={**labels, "error_type": "invalid_json"},
                )
                raise ProviderResponseError(
                    "Risposta provider non JSON",
                    endpoint=endpoint,
                ) from exc

            if not isinstance(payload, dict):
                raise ProviderResponseError(
                    "Risposta provider non è un oggetto",
                    endpoint=endpoint,
                )

            if errors_indicate_rate_limit(payload.get("errors")):
                metrics.incr(
                    PROVIDER_REQUEST_ERRORS_TOTAL,
                    labels={**labels, "error_type": "rate_limit"},
                )
                if self._pause_for_rate_limit(
                    endpoint=endpoint,
                    pause_count=rate_limit_pauses,
                    override=None,
                    metrics=metrics,
                    labels=labels,
                ):
                    rate_limit_pauses += 1
                    continue
                raise ProviderRateLimitError(
                    "Quota API-Football esaurita o rate limit attivo dopo pause ripetute.",
                    endpoint=endpoint,
                    remaining=rate_limit.remaining,
                )

            logger.info(
                "provider_request_ok",
                extra={
                    "provider": PROVIDER_NAME,
                    "endpoint": endpoint,
                    "status": status,
                    "results": payload.get("results"),
                    "page": (payload.get("paging") or {}).get("current")
                    if isinstance(payload.get("paging"), dict)
                    else None,
                    "rate_limit_remaining": rate_limit.remaining,
                },
            )
            return parse_envelope(
                payload,
                endpoint=endpoint,
                rate_limit=rate_limit,
                http_status=status,
                raise_on_errors=True,
            )

    def _pause_for_rate_limit(
        self,
        *,
        endpoint: str,
        pause_count: int,
        override: float | None,
        metrics: Any,
        labels: dict[str, str],
    ) -> bool:
        """Sleep one minute (or Retry-After) and resume. False when pause budget exhausted."""
        if pause_count >= self._max_rate_limit_pauses:
            return False
        delay = self._rate_limit_pause if override is None else max(float(override), 0.0)
        logger.warning(
            "provider_rate_limit_pause",
            extra={
                "provider": PROVIDER_NAME,
                "endpoint": endpoint,
                "pause_seconds": delay,
                "pause_index": pause_count + 1,
                "max_pauses": self._max_rate_limit_pauses,
            },
        )
        metrics.incr(PROVIDER_RATE_LIMIT_PAUSES_TOTAL, labels={"provider": PROVIDER_NAME})
        metrics.incr(PROVIDER_RETRIES_TOTAL, labels=labels)
        time.sleep(delay)
        return True

    def _sleep_backoff(self, attempt: int, *, override: float | None = None) -> None:
        delay = override if override is not None else self._retry_backoff * (2 ** (attempt - 1))
        if delay > 0:
            time.sleep(delay)


def _parse_retry_after(headers: Any) -> float | None:
    raw = None
    if hasattr(headers, "get"):
        raw = headers.get("Retry-After") or headers.get("retry-after")
    if raw is None:
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def build_client_from_settings(settings: Any) -> ApiFootballClient:
    """Factory from ``ApiSettings`` (or any object with resolved key + optional fields)."""
    key = None
    if hasattr(settings, "resolved_api_football_key"):
        key = settings.resolved_api_football_key()
    base_url = getattr(settings, "api_football_base_url", DEFAULT_BASE_URL) or DEFAULT_BASE_URL
    timeout = float(getattr(settings, "api_football_timeout_seconds", 30.0) or 30.0)
    max_retries = int(getattr(settings, "api_football_max_retries", 3) or 0)
    backoff = float(getattr(settings, "api_football_retry_backoff_seconds", 1.0) or 0.0)
    rpm = int(
        getattr(settings, "api_football_requests_per_minute", DEFAULT_REQUESTS_PER_MINUTE)
        or DEFAULT_REQUESTS_PER_MINUTE
    )
    pause = float(
        getattr(
            settings,
            "api_football_rate_limit_pause_seconds",
            DEFAULT_RATE_LIMIT_PAUSE_SECONDS,
        )
        or DEFAULT_RATE_LIMIT_PAUSE_SECONDS
    )
    return ApiFootballClient(
        api_key=key,
        base_url=str(base_url),
        timeout_seconds=timeout,
        max_retries=max_retries,
        retry_backoff_seconds=backoff,
        requests_per_minute=rpm,
        rate_limit_pause_seconds=pause,
    )
