"""Parse and validate API-Football v3 response envelopes."""

from __future__ import annotations

from typing import Any

from sports_data.provider.errors import ProviderRateLimitError, ProviderResponseError
from sports_data.provider.types import ProviderEnvelope, ProviderPaging, ProviderRateLimit


def _as_int(value: Any, default: int = 0) -> int:
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def errors_indicate_rate_limit(errors: Any) -> bool:
    """Detect API-Football rate-limit payloads returned with HTTP 200 + errors body."""
    if errors is None:
        return False
    if isinstance(errors, dict):
        for key, value in errors.items():
            key_l = str(key).lower().replace("_", "").replace("-", "")
            if "ratelimit" in key_l:
                return True
            if isinstance(value, str) and "too many requests" in value.lower():
                return True
            if errors_indicate_rate_limit(value):
                return True
        return False
    if isinstance(errors, list):
        return any(errors_indicate_rate_limit(item) for item in errors)
    if isinstance(errors, str):
        text = errors.lower()
        return "too many requests" in text or "rate limit" in text
    return False


def parse_rate_limit_headers(headers: dict[str, str] | Any) -> ProviderRateLimit:
    """Extract rate-limit info without logging header values that may be sensitive."""

    def _get(*names: str) -> int | None:
        for name in names:
            raw = None
            if hasattr(headers, "get"):
                raw = headers.get(name) or headers.get(name.lower())
            if raw is None:
                continue
            try:
                return int(raw)
            except (TypeError, ValueError):
                continue
        return None

    return ProviderRateLimit(
        limit=_get("x-ratelimit-requests-limit", "X-RateLimit-Requests-Limit"),
        remaining=_get(
            "x-ratelimit-requests-remaining",
            "X-RateLimit-Requests-Remaining",
        ),
    )


def parse_envelope(
    payload: dict[str, Any],
    *,
    endpoint: str | None = None,
    rate_limit: ProviderRateLimit | None = None,
    http_status: int | None = None,
    raise_on_errors: bool = True,
) -> ProviderEnvelope:
    """Parse a provider JSON body into a typed envelope.

    Parameters
    ----------
    raise_on_errors:
        When True, non-empty ``errors`` raise ``ProviderResponseError``.
    """
    if not isinstance(payload, dict):
        raise ProviderResponseError(
            "Payload provider non è un oggetto JSON",
            endpoint=endpoint,
        )

    get_path = payload.get("get")
    resolved_endpoint = endpoint
    if isinstance(get_path, str) and get_path:
        resolved_endpoint = get_path if get_path.startswith("/") else f"/{get_path}"
    if not resolved_endpoint:
        raise ProviderResponseError("Endpoint provider assente nell'envelope", endpoint=None)

    parameters_raw = payload.get("parameters") or {}
    if not isinstance(parameters_raw, dict):
        raise ProviderResponseError(
            "Campo parameters non valido",
            endpoint=resolved_endpoint,
        )
    parameters = {str(k): str(v) for k, v in parameters_raw.items()}

    paging_raw = payload.get("paging") or {}
    if not isinstance(paging_raw, dict):
        paging_raw = {}
    paging = ProviderPaging(
        current=_as_int(paging_raw.get("current"), 1),
        total=max(_as_int(paging_raw.get("total"), 1), 1),
    )

    response = payload.get("response")
    if response is None:
        response = []
    if not isinstance(response, list):
        raise ProviderResponseError(
            "Campo response non è una lista",
            endpoint=resolved_endpoint,
            provider_errors=payload.get("errors"),
        )

    results = _as_int(payload.get("results"), len(response))
    errors = payload.get("errors")
    envelope = ProviderEnvelope(
        endpoint=resolved_endpoint,
        parameters=parameters,
        errors=errors if errors is not None else [],
        results=results,
        paging=paging,
        response=response,
        rate_limit=rate_limit,
        http_status=http_status,
        raw=payload,
    )
    if raise_on_errors and envelope.has_errors:
        if errors_indicate_rate_limit(errors):
            raise ProviderRateLimitError(
                "Quota API-Football esaurita o rate limit attivo. Riprova tra circa un minuto.",
                endpoint=resolved_endpoint,
            )
        raise ProviderResponseError(
            "Il provider ha restituito errori nell'envelope",
            endpoint=resolved_endpoint,
            provider_errors=errors,
        )
    return envelope


def merge_envelopes(pages: list[ProviderEnvelope]) -> ProviderEnvelope:
    """Merge paginated envelopes into one logical response (idempotent concat)."""
    if not pages:
        raise ProviderResponseError("Nessuna pagina da unire")
    first = pages[0]
    if len(pages) == 1:
        return first
    combined: list[Any] = []
    for page in pages:
        if page.endpoint != first.endpoint:
            raise ProviderResponseError(
                "Pagine con endpoint inconsistenti",
                endpoint=first.endpoint,
            )
        combined.extend(page.response)
    return ProviderEnvelope(
        endpoint=first.endpoint,
        parameters=first.parameters,
        errors=[],
        results=len(combined),
        paging=ProviderPaging(current=1, total=1),
        response=combined,
        rate_limit=pages[-1].rate_limit or first.rate_limit,
        http_status=pages[-1].http_status or first.http_status,
        raw={
            "get": first.endpoint.lstrip("/"),
            "parameters": first.parameters,
            "errors": [],
            "results": len(combined),
            "paging": {"current": 1, "total": 1},
            "response": combined,
        },
    )
