"""Homologate and correct fantasy turns (EP07-07 / FR-OMO-01).

FR-OMO-01: pubblica il risultato provvisorio, acquisisce eventuali
correzioni, ricalcola e notifica le variazioni, quindi omologa. Un turno
omologato non cambia più per nuove versioni della formula; solo una
correzione esplicita — con permesso, motivo e traccia in audit — può
riaprirlo per un nuovo ricalcolo.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import update
from sqlalchemy.orm import Session

from auth.exceptions import ValidationAuthError
from database.enums import FantasyRoundHomologationStatus, LeagueAuditAction, NotificationCategory
from fantasy_ratings.config import default_formula_config
from fantasy_turns.models import FantasyRound
from fantasy_turns.readiness import evaluate_round_readiness
from leagues.models.league_audit_event import LeagueAuditEvent
from notifications.recipients import user_ids_for_league
from notifications.service import NotificationService
from observability.context import get_correlation_id


@dataclass(frozen=True)
class HomologationResult:
    round_id: UUID
    homologation_status: str
    homologated_at: datetime | None
    formula_version: str | None


def homologate_round(
    session: Session,
    *,
    round_id: UUID,
    actor_id: UUID | None,
    automatic: bool = False,
) -> HomologationResult:
    """Omologa un turno: richiede tutte le partite terminate (dato reale finale).

    La transizione è una UPDATE condizionale sullo stato corrente: sotto
    concorrenza, un solo chiamante la vede applicata (``rowcount == 1``); gli
    altri ricevono ``round_already_homologated`` invece di sovrascriversi a
    vicenda o duplicare l'evento di audit.
    """
    fantasy_round = session.get(FantasyRound, round_id)
    if fantasy_round is None:
        raise ValidationAuthError("Turno non trovato.", code="turn_not_found")

    readiness = evaluate_round_readiness(session, round_id=round_id)
    if not readiness.all_fixtures_finished:
        raise ValidationAuthError(
            "Non tutte le partite del turno sono terminate: il risultato resta provvisorio.",
            code="round_not_final",
        )
    if not readiness.all_statistics_available:
        raise ValidationAuthError(
            "Le partite sono terminate ma mancano ancora statistiche giocatore definitive.",
            code="round_statistics_pending",
        )

    now = datetime.now(UTC)
    formula_version = default_formula_config().version
    outcome = session.execute(
        update(FantasyRound)
        .where(
            FantasyRound.id == round_id,
            FantasyRound.homologation_status == FantasyRoundHomologationStatus.PROVISIONAL,
        )
        .values(
            homologation_status=FantasyRoundHomologationStatus.HOMOLOGATED,
            homologated_at=now,
            homologated_by_user_id=actor_id,
            homologation_formula_version=formula_version,
        )
    )
    if outcome.rowcount == 0:
        raise ValidationAuthError("Il turno è già omologato.", code="round_already_homologated")

    # L'UPDATE condizionale sopra e' un'espressione Core: non aggiorna in modo
    # affidabile gli attributi dell'oggetto ORM gia' caricato in sessione.
    # Lo si scade cosi' che ogni accesso successivo rilegga lo stato reale.
    session.expire(fantasy_round)

    session.add(
        LeagueAuditEvent(
            league_id=fantasy_round.league_id,
            actor_id=actor_id,
            action=LeagueAuditAction.FANTASY_ROUND_HOMOLOGATED,
            correlation_id=get_correlation_id(),
            details={
                "roundId": str(round_id),
                "formulaVersion": formula_version,
                "source": "automatic_live_pipeline" if automatic else "manual_operator",
            },
        )
    )
    notifications = NotificationService(session)
    for _, user_id in user_ids_for_league(session, fantasy_round.league_id):
        notifications.create_notification(
            user_id=user_id,
            category=NotificationCategory.RISULTATI,
            template_key="risultati.omologazione",
            template_version=1,
            params={"round_number": fantasy_round.number},
            dedup_key=f"round_homologated:{round_id}:{now.isoformat()}:{user_id}",
        )
    session.flush()

    # Un turno omologato è il "verdetto" che sblocca il successivo
    # (EP-turni-automazione): l'apertura non aspetta più il giro orario del
    # cron, scatta qui — sia che l'omologazione sia manuale sia automatica,
    # perché questo è l'unico punto di ingresso per entrambe.
    from fantasy_turns.service import FantasyTurnService

    FantasyTurnService(session).try_open_next_round(
        league_id=fantasy_round.league_id,
        current_number=fantasy_round.number,
        actor_id=actor_id,
    )
    session.flush()

    return HomologationResult(
        round_id=round_id,
        homologation_status=FantasyRoundHomologationStatus.HOMOLOGATED.value,
        homologated_at=now,
        formula_version=formula_version,
    )


def apply_round_correction(
    session: Session,
    *,
    round_id: UUID,
    actor_id: UUID,
    reason: str,
) -> HomologationResult:
    """Riapre un turno omologato per un ricalcolo controllato (FR-OMO-01 §Eccezioni).

    Non ricalcola nulla da sola: riporta il turno a "provvisorio" in modo
    atomico e auditato, cosi' le chiamate successive a compute_fixture_ratings
    / compute_round_effective_lineups / compute_round_results tornano ad
    essere ammesse. Il turno resta "provvisorio" finche' un nuovo
    ``homologate_round`` non lo richiude esplicitamente.
    """
    cleaned_reason = reason.strip()
    if not cleaned_reason:
        raise ValidationAuthError(
            "Indica il motivo della correzione.",
            code="correction_reason_required",
        )

    fantasy_round = session.get(FantasyRound, round_id)
    if fantasy_round is None:
        raise ValidationAuthError("Turno non trovato.", code="turn_not_found")

    previous_homologated_at = fantasy_round.homologated_at
    previous_formula_version = fantasy_round.homologation_formula_version

    outcome = session.execute(
        update(FantasyRound)
        .where(
            FantasyRound.id == round_id,
            FantasyRound.homologation_status == FantasyRoundHomologationStatus.HOMOLOGATED,
        )
        .values(
            homologation_status=FantasyRoundHomologationStatus.PROVISIONAL,
            homologated_at=None,
            homologated_by_user_id=None,
            homologation_formula_version=None,
        )
    )
    if outcome.rowcount == 0:
        raise ValidationAuthError(
            "Il turno non è omologato: non serve una correzione per ricalcolarlo.",
            code="round_not_homologated",
        )

    session.expire(fantasy_round)

    session.add(
        LeagueAuditEvent(
            league_id=fantasy_round.league_id,
            actor_id=actor_id,
            action=LeagueAuditAction.FANTASY_ROUND_CORRECTION_APPLIED,
            correlation_id=get_correlation_id(),
            details={
                "roundId": str(round_id),
                "reason": cleaned_reason,
                "previousHomologatedAt": (
                    previous_homologated_at.isoformat() if previous_homologated_at else None
                ),
                "previousFormulaVersion": previous_formula_version,
            },
        )
    )
    corrected_homologation = (
        previous_homologated_at.isoformat() if previous_homologated_at else "na"
    )
    notifications = NotificationService(session)
    for _, user_id in user_ids_for_league(session, fantasy_round.league_id):
        notifications.create_notification(
            user_id=user_id,
            category=NotificationCategory.RISULTATI,
            template_key="risultati.correzione",
            template_version=1,
            params={"round_number": fantasy_round.number},
            dedup_key=f"round_correction:{round_id}:{corrected_homologation}:{user_id}",
        )
    session.flush()
    return HomologationResult(
        round_id=round_id,
        homologation_status=FantasyRoundHomologationStatus.PROVISIONAL.value,
        homologated_at=None,
        formula_version=None,
    )
