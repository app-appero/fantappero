"""Esito dei giri dei job: come si legge dal risultato o dall'eccezione (release 1.4)."""

from __future__ import annotations

from sports_data.provider.errors import (
    ProviderAuthError,
    ProviderConfigError,
    ProviderHttpError,
    ProviderRateLimitError,
)
from system_jobs.catalog import SYSTEM_JOBS
from system_jobs.runs import (
    OUTCOME_FAILED,
    OUTCOME_OK,
    REASON_MAX_LENGTH,
    clip_reason,
    job_key_for_task,
    outcome_from_result,
    reason_from_exception,
)


def test_every_catalog_task_maps_to_its_job() -> None:
    for spec in SYSTEM_JOBS:
        assert job_key_for_task(spec.task) == spec.key
    assert job_key_for_task("mail.send_email") is None
    assert job_key_for_task(None) is None


def test_plain_results_are_ok() -> None:
    assert outcome_from_result({"expired": 3}).outcome == OUTCOME_OK
    assert outcome_from_result(0).outcome == OUTCOME_OK
    assert outcome_from_result(None).outcome == OUTCOME_OK
    assert outcome_from_result({"status": "completed"}).outcome == OUTCOME_OK
    assert outcome_from_result({"failed": 0, "leagues": 3}).outcome == OUTCOME_OK


def test_failed_status_in_the_result_is_a_failure_with_its_code() -> None:
    result = outcome_from_result({"status": "failed", "code": "provider_rate_limited"})
    assert result.outcome == OUTCOME_FAILED
    assert result.reason is not None
    assert "provider_rate_limited" in result.reason

    error = outcome_from_result({"status": "error", "error_code": "ProviderHttpError"})
    assert error.outcome == OUTCOME_FAILED
    assert "ProviderHttpError" in (error.reason or "")


def test_some_leagues_not_refreshed_is_a_failure() -> None:
    result = outcome_from_result({"leagues": 4, "refreshed": 3, "failed": 1})
    assert result.outcome == OUTCOME_FAILED
    assert result.reason == "Non riuscito per 1 leghe su 4."


def test_provider_errors_get_a_readable_reason() -> None:
    assert reason_from_exception(ProviderRateLimitError("429")).startswith(
        "Fornitore sportivo: troppe richieste"
    )
    assert "chiave mancante" in reason_from_exception(ProviderConfigError("missing"))
    assert "chiave non accettata" in reason_from_exception(ProviderAuthError("401"))
    assert "non raggiungibile" in reason_from_exception(ProviderHttpError("down", status_code=503))


def test_other_errors_keep_type_and_message() -> None:
    assert reason_from_exception(RuntimeError("boom")) == "RuntimeError: boom"
    assert reason_from_exception(ValueError()) == "ValueError"
    assert reason_from_exception(None) == "Errore sconosciuto."


def test_long_reasons_are_clipped() -> None:
    clipped = clip_reason("x" * (REASON_MAX_LENGTH + 50))
    assert clipped is not None
    assert len(clipped) == REASON_MAX_LENGTH
    assert clipped.endswith("…")
    assert clip_reason("  a\n  b ") == "a b"
    assert clip_reason("   ") is None
