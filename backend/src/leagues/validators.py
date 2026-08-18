"""Validation rules for league creation and regulation configuration."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from auth.exceptions import ValidationAuthError
from database.enums import LeagueMemberRole, LeagueState
from fantasy_lineups.rules import (
    MAX_AUTOMATIC_SUBSTITUTIONS,
    MIN_AUTOMATIC_SUBSTITUTIONS,
    coerce_max_automatic_substitutions,
)
from fantasy_ratings.eligibility import (
    MAX_MINUTES_THRESHOLD,
    MIN_MINUTES_THRESHOLD,
    coerce_minutes_threshold,
)

_LEAGUE_NAME_MAX_LENGTH = 120
MIN_COMPETITIONS = 3
_SEASON_YEAR_MIN = 2020
STANDARD_PRESET_NAME = "standard"
MIN_PARTICIPANTS = 4
MAX_PARTICIPANTS = 10
STANDARD_PARTICIPANT_COUNT = 8
STANDARD_ROSTER_SIZE = 35
STANDARD_GOALKEEPERS = 3
STANDARD_DEFENDERS = 11
STANDARD_MIDFIELDERS = 11
STANDARD_FORWARDS = 10
STANDARD_TOTAL_CREDITS = 1000
MIN_INVITE_EXPIRY_DAYS = 1
MAX_INVITE_EXPIRY_DAYS = 30

LEAGUE_TRANSITIONS: dict[LeagueState, tuple[LeagueState, ...]] = {
    LeagueState.DRAFT: (LeagueState.CONFIGURING,),
    LeagueState.CONFIGURING: (LeagueState.AUCTION,),
    LeagueState.AUCTION: (LeagueState.CONFIGURING, LeagueState.ACTIVE),
    LeagueState.ACTIVE: (LeagueState.CONCLUDED,),
    LeagueState.CONCLUDED: (LeagueState.ARCHIVED,),
    LeagueState.ARCHIVED: (),
}
CONFIGURABLE_LEAGUE_STATES = frozenset((LeagueState.DRAFT, LeagueState.CONFIGURING))
# Hard-delete allowed only before auction/season start (EP03-05-EXT).
# configuring is included: no irreversible gameplay yet; archive remains post-season path.
DELETABLE_LEAGUE_STATES = frozenset((LeagueState.DRAFT, LeagueState.CONFIGURING))


@dataclass(frozen=True)
class LifecycleBlocker:
    code: str
    message: str


def validate_league_name(name: str) -> str:
    cleaned = name.strip()
    if not cleaned:
        raise ValidationAuthError("Inserisci un nome per la lega.", code="invalid_league_name")
    if len(cleaned) > _LEAGUE_NAME_MAX_LENGTH:
        raise ValidationAuthError(
            "Il nome della lega è troppo lungo.",
            code="invalid_league_name",
        )
    return cleaned


def validate_season_year(season_year: int) -> int:
    max_year = datetime.now(UTC).year + 1
    if season_year < _SEASON_YEAR_MIN or season_year > max_year:
        raise ValidationAuthError(
            "Seleziona una stagione valida.",
            code="invalid_season_year",
        )
    return season_year


def validate_competition_ids(competition_ids: list[UUID]) -> list[UUID]:
    if len(competition_ids) != len(set(competition_ids)):
        raise ValidationAuthError(
            "Seleziona ogni campionato una sola volta.",
            code="duplicate_competitions",
        )
    if len(competition_ids) < MIN_COMPETITIONS:
        raise ValidationAuthError(
            f"Seleziona almeno {MIN_COMPETITIONS} campionati.",
            code="insufficient_competitions",
        )
    return competition_ids


def validate_preset_name(preset_name: str) -> str:
    cleaned = preset_name.strip().lower()
    if cleaned != STANDARD_PRESET_NAME:
        raise ValidationAuthError(
            "È disponibile solo il preset Standard.",
            code="invalid_rules_preset",
        )
    return cleaned


def validate_participant_count(participant_count: int) -> int:
    if participant_count < MIN_PARTICIPANTS or participant_count > MAX_PARTICIPANTS:
        raise ValidationAuthError(
            f"Il numero partecipanti deve essere tra {MIN_PARTICIPANTS} e {MAX_PARTICIPANTS}.",
            code="invalid_participant_count",
        )
    return participant_count


def validate_total_credits(total_credits: int) -> int:
    if total_credits <= 0:
        raise ValidationAuthError(
            "I crediti devono essere maggiori di zero.",
            code="invalid_total_credits",
        )
    return total_credits


def validate_minutes_threshold(value: int) -> int:
    try:
        return coerce_minutes_threshold(value)
    except ValueError as exc:
        raise ValidationAuthError(
            (
                "La soglia minuti deve essere tra "
                f"{MIN_MINUTES_THRESHOLD} e {MAX_MINUTES_THRESHOLD}."
            ),
            code="invalid_minutes_threshold",
        ) from exc


def validate_max_automatic_substitutions(value: int) -> int:
    try:
        return coerce_max_automatic_substitutions(value)
    except ValueError as exc:
        raise ValidationAuthError(
            (
                "Il limite di sostituzioni automatiche deve essere tra "
                f"{MIN_AUTOMATIC_SUBSTITUTIONS} e {MAX_AUTOMATIC_SUBSTITUTIONS}."
            ),
            code="invalid_max_automatic_substitutions",
        ) from exc


def validate_refund_percent(value: int, *, field: str) -> int:
    """Bounds for the market release refund percentages (EP08-04 / FR-MKT-02)."""
    if value < 0 or value > 100:
        raise ValidationAuthError(
            f"La percentuale {field} deve essere tra 0 e 100.",
            code="invalid_refund_percent",
        )
    return value


def validate_invite_expiry_days(expires_in_days: int) -> int:
    if expires_in_days < MIN_INVITE_EXPIRY_DAYS or expires_in_days > MAX_INVITE_EXPIRY_DAYS:
        raise ValidationAuthError(
            (
                "La scadenza dell'invito deve essere compresa tra "
                f"{MIN_INVITE_EXPIRY_DAYS} e {MAX_INVITE_EXPIRY_DAYS} giorni."
            ),
            code="invalid_invite_expiry",
        )
    return expires_in_days


def normalize_invite_code(code: str) -> str:
    normalized = code.strip().upper().replace("-", "")
    if len(normalized) != 10 or not normalized.isalnum():
        raise ValidationAuthError(
            "Il codice invito non è valido.",
            code="invalid_invite",
        )
    return normalized


def validate_invite_credential(*, token: str | None, code: str | None) -> tuple[str, str]:
    cleaned_token = token.strip() if token else ""
    cleaned_code = code.strip() if code else ""
    if bool(cleaned_token) == bool(cleaned_code):
        raise ValidationAuthError(
            "Inserisci un solo link o codice invito.",
            code="invalid_invite",
        )
    if cleaned_token:
        return "token", cleaned_token
    return "code", normalize_invite_code(cleaned_code)


def validate_member_removal(role: LeagueMemberRole) -> None:
    if role == LeagueMemberRole.OWNER:
        raise ValidationAuthError(
            "Trasferisci prima il ruolo di amministratore.",
            code="cannot_remove_admin",
        )


def validate_admin_transfer_target(role: LeagueMemberRole) -> None:
    if role != LeagueMemberRole.MEMBER:
        raise ValidationAuthError(
            "Seleziona un partecipante a cui trasferire il ruolo.",
            code="invalid_transfer_target",
        )


def validate_league_transition(current: LeagueState, target: LeagueState) -> bool:
    """Return False for an idempotent no-op, reject transitions outside the state graph."""
    if current == target:
        return False
    if target not in LEAGUE_TRANSITIONS[current]:
        raise ValidationAuthError(
            f"Il passaggio da {current.value} a {target.value} non è consentito.",
            code="invalid_league_transition",
        )
    return True


def validate_configurable_league_state(state: LeagueState, *, subject: str) -> None:
    if state not in CONFIGURABLE_LEAGUE_STATES:
        raise ValidationAuthError(
            f"Puoi gestire {subject} solo durante la bozza o la configurazione.",
            # Keep the existing public code for backward-compatible clients.
            code="league_not_draft",
        )


def validate_league_deletable(state: LeagueState) -> None:
    if state not in DELETABLE_LEAGUE_STATES:
        raise ValidationAuthError(
            "La lega non può essere eliminata in questo stato. "
            "Usa l'archiviazione a fine stagione.",
            code="league_not_deletable",
        )


def configuration_blockers(
    *,
    rules_valid: bool,
    competition_count: int,
    membership_count: int,
    participant_count: int | None,
    owner_count: int,
) -> list[LifecycleBlocker]:
    blockers: list[LifecycleBlocker] = []
    if not rules_valid:
        blockers.append(
            LifecycleBlocker(
                code="rules_invalid",
                message="Completa un regolamento valido prima di avviare l'asta.",
            )
        )
    if competition_count < MIN_COMPETITIONS:
        blockers.append(
            LifecycleBlocker(
                code="insufficient_competitions",
                message=f"Seleziona almeno {MIN_COMPETITIONS} campionati.",
            )
        )
    if participant_count is None or membership_count != participant_count:
        blockers.append(
            LifecycleBlocker(
                code="participant_count_mismatch",
                message="Il numero di partecipanti deve coincidere con quello del regolamento.",
            )
        )
    if owner_count != 1:
        blockers.append(
            LifecycleBlocker(
                code="league_admin_required",
                message="La lega deve avere esattamente un amministratore.",
            )
        )
    return blockers


def auction_activation_blockers(
    *,
    calendar_configured: bool = False,
    roster_blockers: list[LifecycleBlocker] | None = None,
) -> list[LifecycleBlocker]:
    """Blockers for auction → active.

    Calendar is owned by EP03-06. Roster/credit checks are supplied by EP05-05
    (``roster_blockers``); when omitted, keep legacy placeholders for unit tests.
    """
    blockers: list[LifecycleBlocker] = []
    if not calendar_configured:
        blockers.append(
            LifecycleBlocker(
                code="calendar_not_configured",
                message="Genera il calendario prima di avviare la stagione.",
            )
        )
    if roster_blockers is not None:
        blockers.extend(roster_blockers)
    else:
        blockers.extend(
            [
                LifecycleBlocker(
                    code="fantasy_teams_not_configured",
                    message="Completa squadre e rose prima di avviare la stagione.",
                ),
                LifecycleBlocker(
                    code="credits_not_configured",
                    message="Verifica i crediti di tutte le squadre prima di avviare la stagione.",
                ),
            ]
        )
    return blockers


def validate_calendar_generation_state(state: LeagueState) -> None:
    if state not in CONFIGURABLE_LEAGUE_STATES and state != LeagueState.AUCTION:
        raise ValidationAuthError(
            "Puoi generare il calendario solo in configurazione o durante l'asta.",
            code="league_calendar_locked",
        )


def validate_calendar_participant_alignment(
    *,
    membership_count: int,
    participant_count: int | None,
) -> None:
    if participant_count is None:
        raise ValidationAuthError(
            "Completa il regolamento prima di generare il calendario.",
            code="rules_invalid",
        )
    if membership_count != participant_count:
        raise ValidationAuthError(
            "Il numero di partecipanti iscritti deve coincidere con il regolamento.",
            code="participant_count_mismatch",
        )
    validate_participant_count(membership_count)


def validate_standard_roster(
    *,
    roster_size: int,
    goalkeepers: int,
    defenders: int,
    midfielders: int,
    forwards: int,
) -> None:
    if roster_size != STANDARD_ROSTER_SIZE:
        raise ValidationAuthError(
            f"La rosa deve contenere esattamente {STANDARD_ROSTER_SIZE} giocatori.",
            code="invalid_roster_size",
        )
    if (
        goalkeepers != STANDARD_GOALKEEPERS
        or defenders != STANDARD_DEFENDERS
        or midfielders != STANDARD_MIDFIELDERS
        or forwards != STANDARD_FORWARDS
    ):
        raise ValidationAuthError(
            "La composizione rosa deve essere 3P-11D-11C-10A.",
            code="invalid_roster_distribution",
        )
    if goalkeepers + defenders + midfielders + forwards != roster_size:
        raise ValidationAuthError(
            "La somma dei ruoli deve coincidere con la dimensione della rosa.",
            code="invalid_roster_distribution",
        )
