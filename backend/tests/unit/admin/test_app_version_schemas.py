"""Validazione della versione dell'app Android impostata dall'operatore."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from admin.schemas import AdminAndroidAppVersionUpdateRequest

VALID = {
    "latestVersionName": "1.3.0",
    "latestVersionCode": 4,
    "downloadUrl": "https://drive.google.com/file/d/abc/view",
}


def test_valori_validi_ripuliti() -> None:
    body = AdminAndroidAppVersionUpdateRequest.model_validate(
        {
            **VALID,
            "latestVersionName": " 1.3 ",
            "downloadUrl": " https://example.com/app.apk ",
            "message": "  ",
        }
    )
    assert body.latest_version_name == "1.3"
    assert body.download_url == "https://example.com/app.apk"
    assert body.message is None


@pytest.mark.parametrize(
    "url", ["http://example.com/app.apk", "ftp://example.com", "https:/x", "example.com/app.apk"]
)
def test_solo_link_https(url: str) -> None:
    with pytest.raises(ValidationError):
        AdminAndroidAppVersionUpdateRequest.model_validate({**VALID, "downloadUrl": url})


@pytest.mark.parametrize("code", [0, -1, 2_100_000_001, True, "4"])
def test_version_code_intero_positivo(code: object) -> None:
    with pytest.raises(ValidationError):
        AdminAndroidAppVersionUpdateRequest.model_validate({**VALID, "latestVersionCode": code})


@pytest.mark.parametrize("name", ["", "1.2.3.4.5", "v1.3", "1.3-beta"])
def test_nome_versione_numerico(name: str) -> None:
    with pytest.raises(ValidationError):
        AdminAndroidAppVersionUpdateRequest.model_validate({**VALID, "latestVersionName": name})
