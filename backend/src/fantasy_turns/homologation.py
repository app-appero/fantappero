"""Provisional/homologated guard for a fantasy turn (EP07-07 / FR-OMO-01).

"Turni omologati non cambiano per nuove versioni della formula": once a
round is homologated, the ordinary recompute entry points (voto statistico,
formazione effettiva, risultato, classifica) must refuse to silently mutate
its data. Only ``fantasy_turns.homologation_service.apply_round_correction``
may reopen it, always audited with a reason.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from auth.exceptions import ValidationAuthError
from database.enums import FantasyRoundHomologationStatus
from fantasy_turns.models import FantasyRound, FantasyRoundFixture

ROUND_HOMOLOGATED_MESSAGE = (
    "Il turno è omologato: i dati non cambiano più per nuove versioni della "
    "formula. Usa una correzione per ricalcolare (motivo obbligatorio)."
)


def is_homologated(fantasy_round: FantasyRound) -> bool:
    return fantasy_round.homologation_status == FantasyRoundHomologationStatus.HOMOLOGATED


def assert_round_not_homologated(fantasy_round: FantasyRound) -> None:
    """Blocca un ricalcolo ordinario (EP07-04/05) su un turno già omologato."""
    if is_homologated(fantasy_round):
        raise ValidationAuthError(ROUND_HOMOLOGATED_MESSAGE, code="round_homologated")


def assert_fixture_not_homologated(session: Session, *, fixture_id: UUID) -> None:
    """Blocca il ricalcolo del voto statistico (EP07-01/02/03) di una fixture
    che appartiene a un turno già omologato, in qualunque lega.
    """
    homologated = session.execute(
        select(FantasyRound.id)
        .join(FantasyRoundFixture, FantasyRoundFixture.round_id == FantasyRound.id)
        .where(
            FantasyRoundFixture.fixture_id == fixture_id,
            FantasyRoundFixture.excluded_at.is_(None),
            FantasyRound.homologation_status == FantasyRoundHomologationStatus.HOMOLOGATED,
        )
        .limit(1)
    ).first()
    if homologated is not None:
        raise ValidationAuthError(ROUND_HOMOLOGATED_MESSAGE, code="round_homologated")
