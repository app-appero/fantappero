"""Quale app ha fatto la richiesta e quando riscriverla (release 1.4, Rosario 23/11)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app_usage.models import SOURCE_HEADER, SOURCE_USER_AGENT, SOURCE_VERSION_CHECK
from app_usage.recorder import (
    RECORD_INTERVAL,
    AppObservation,
    observe,
    reset_app_usage_throttle,
    should_record,
)

OKHTTP = {"user-agent": "okhttp/4.12.0"}
CHROME = {"user-agent": "Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 Chrome/131.0"}
NOW = datetime(2026, 11, 23, 12, 0, tzinfo=UTC)


@pytest.fixture(autouse=True)
def _fresh_throttle():
    reset_app_usage_throttle()
    yield
    reset_app_usage_throttle()


def test_le_intestazioni_della_1_4_danno_la_versione_esatta() -> None:
    headers = {
        **OKHTTP,
        "x-app-version": "1.4.0",
        "x-app-version-code": "5",
        "x-app-platform": "android",
    }
    assert observe(headers, method="GET", path="/leagues") == AppObservation(
        platform="android", source=SOURCE_HEADER, version_name="1.4.0", version_code=5
    )
    # Anche su /app/version vince la versione esatta.
    assert observe(headers, method="GET", path="/app/version").source == SOURCE_HEADER


def test_intestazioni_parziali_o_rovinate() -> None:
    # Senza nome si tiene il versionCode; piattaforma sconosciuta = Android.
    only_code = observe(
        {"x-app-version-code": " 7 ", "x-app-platform": "symbian"}, method="GET", path="/x"
    )
    assert only_code == AppObservation("android", SOURCE_HEADER, None, 7)
    assert observe(
        {"x-app-version-code": "5", "x-app-version": "<script>"}, method="GET", path="/x"
    ) == AppObservation("android", SOURCE_HEADER, None, 5)
    assert observe(
        {"x-app-version-code": "5", "x-app-platform": "ios"}, method="GET", path="/x"
    ) == (AppObservation("ios", SOURCE_HEADER, None, 5))
    # versionCode non valido: si torna alle regole senza intestazioni.
    for bad in ("0", "-1", "abc", "1.5", "99999999999", ""):
        headers = {**OKHTTP, "x-app-version-code": bad}
        assert observe(headers, method="GET", path="/x").source == SOURCE_USER_AGENT, bad


def test_app_version_senza_intestazioni_vale_app_1_2_o_1_3() -> None:
    assert observe(OKHTTP, method="GET", path="/app/version") == AppObservation(
        "android", SOURCE_VERSION_CHECK
    )
    assert observe({}, method="GET", path="/app/version/").source == SOURCE_VERSION_CHECK
    # Non è la lettura dell'operatore.
    assert observe(OKHTTP, method="GET", path="/admin/app-version").source == SOURCE_USER_AGENT


def test_okhttp_senza_intestazioni_vale_app_versione_non_nota() -> None:
    assert observe(OKHTTP, method="POST", path="/leagues/1/formazione") == AppObservation(
        "android", SOURCE_USER_AGENT
    )


def test_il_sito_non_conta() -> None:
    assert observe(CHROME, method="GET", path="/leagues") is None
    assert observe(CHROME, method="GET", path="/app/version") is None
    assert observe({"user-agent": "python-httpx/0.28"}, method="GET", path="/leagues") is None
    assert observe({}, method="GET", path="/leagues") is None


def test_si_scrive_al_piu_ogni_qualche_minuto() -> None:
    user = uuid4()
    exact = AppObservation("android", SOURCE_HEADER, "1.4.0", 5)
    assert should_record(user, exact, now=NOW) is True
    assert should_record(user, exact, now=NOW + timedelta(seconds=30)) is False
    assert should_record(user, exact, now=NOW + RECORD_INTERVAL - timedelta(seconds=1)) is False
    assert should_record(user, exact, now=NOW + RECORD_INTERVAL + timedelta(seconds=1)) is True
    # Un altro utente ha il suo conto.
    assert should_record(uuid4(), exact, now=NOW) is True


def test_una_novita_si_scrive_subito() -> None:
    user = uuid4()
    assert should_record(user, AppObservation("android", SOURCE_USER_AGENT), now=NOW) is True
    # Più preciso (app 1.2+), poi la versione esatta, poi una versione nuova: subito.
    later = NOW + timedelta(seconds=10)
    assert should_record(user, AppObservation("android", SOURCE_VERSION_CHECK), now=later)
    assert should_record(user, AppObservation("android", SOURCE_HEADER, "1.4.0", 5), now=later)
    assert should_record(user, AppObservation("android", SOURCE_HEADER, "1.4.1", 6), now=later)
    # Meno preciso di quello che si sa già: aspetta come una richiesta uguale.
    assert not should_record(user, AppObservation("android", SOURCE_USER_AGENT), now=later)
    assert not should_record(user, AppObservation("android", SOURCE_VERSION_CHECK), now=later)
    assert not should_record(user, AppObservation("android", SOURCE_HEADER, "1.4.1", 6), now=later)


def test_richieste_alternate_non_scrivono_a_ogni_giro() -> None:
    """Un'app 1.3 chiama /app/version e altre pagine: non si scrive a ogni cambio di fonte."""
    user = uuid4()
    writes = 0
    for second in range(0, 120, 5):
        now = NOW + timedelta(seconds=second)
        source = SOURCE_VERSION_CHECK if second % 10 == 0 else SOURCE_USER_AGENT
        writes += should_record(user, AppObservation("android", source), now=now)
    assert writes == 1
