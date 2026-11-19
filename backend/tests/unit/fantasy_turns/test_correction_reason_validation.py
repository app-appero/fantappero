"""Motivo di correzione turno e di ricalcolo storico: niente NUL né surrogati (QA 19/11).

Il motivo finisce nei dettagli JSONB dell'audit: Postgres rifiuta il byte NUL e la
richiesta rispondeva 500 invece di 422.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from admin.schemas import AdminHistoricalRepairRequest
from fantasy_turns.schemas import ApplyRoundCorrectionRequest

NUL = chr(0)
LONE_SURROGATE = chr(0xD83D)

REQUESTS = [ApplyRoundCorrectionRequest, AdminHistoricalRepairRequest]


@pytest.mark.parametrize("request_model", REQUESTS)
@pytest.mark.parametrize(
    "reason",
    [f"qa{NUL}nul", NUL, f"motivo {LONE_SURROGATE}", ""],
    ids=["nul_in_mezzo", "solo_nul", "surrogato_isolato", "vuoto"],
)
def test_reason_with_invalid_text_is_rejected(request_model: type, reason: str) -> None:
    with pytest.raises(ValidationError):
        request_model.model_validate({"reason": reason})


@pytest.mark.parametrize("request_model", REQUESTS)
def test_valid_reason_is_kept_as_is(request_model: type) -> None:
    reason = "Rettifica voti ufficiali — giornata 7 (è già omologata)"
    assert request_model.model_validate({"reason": reason}).reason == reason
