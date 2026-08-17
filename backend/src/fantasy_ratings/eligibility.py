"""Eleggibilità al voto: soglia minuti configurabile e casi senza voto (EP07-02)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

STANDARD_MINUTES_THRESHOLD = 15
MIN_MINUTES_THRESHOLD = 1
MAX_MINUTES_THRESHOLD = 30
SUBSTITUTION_EVENT_TYPE = "subst"
SECOND_HALF_STOPPAGE_ELAPSED = 90


@dataclass(frozen=True)
class EligibilityDecision:
    eligible: bool
    reason: str


def coerce_minutes_threshold(value: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError("minutes_threshold must be an integer")
    if value < MIN_MINUTES_THRESHOLD or value > MAX_MINUTES_THRESHOLD:
        raise ValueError(
            "minutes_threshold must be between "
            f"{MIN_MINUTES_THRESHOLD} and {MAX_MINUTES_THRESHOLD}"
        )
    return value


def is_second_half_stoppage(elapsed: int | None, extra: int | None) -> bool:
    """True per ingresso nel recupero del secondo tempo (90+ / elapsed>90)."""
    if elapsed is None:
        return False
    if elapsed > SECOND_HALF_STOPPAGE_ELAPSED:
        return True
    return elapsed >= SECOND_HALF_STOPPAGE_ELAPSED and extra is not None and extra > 0


def incoming_subst_player_id(event: dict[str, Any]) -> int | None:
    """API-Football: in ``subst`` ``assist.id`` è chi entra, ``player.id`` chi esce."""
    assist = event.get("assist") if isinstance(event.get("assist"), dict) else {}
    raw = assist.get("id")
    if raw is None:
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def stoppage_entry_player_ids_from_payload(events_payload: dict[str, Any]) -> set[int]:
    ids: set[int] = set()
    for event in events_payload.get("response") or []:
        if not isinstance(event, dict):
            continue
        if str(event.get("type") or "").lower() != SUBSTITUTION_EVENT_TYPE:
            continue
        time_ = event.get("time") if isinstance(event.get("time"), dict) else {}
        elapsed = _as_optional_int(time_.get("elapsed"))
        extra = _as_optional_int(time_.get("extra"))
        if not is_second_half_stoppage(elapsed, extra):
            continue
        player_id = incoming_subst_player_id(event)
        if player_id is not None:
            ids.add(player_id)
    return ids


def evaluate_eligibility(
    *,
    minutes: int | None,
    substitute: bool,
    role: str | None,
    has_relevant_event: bool,
    entered_in_stoppage: bool,
    minutes_threshold: int,
    goalkeeper_starter_always_eligible: bool = True,
) -> EligibilityDecision:
    """Decide se il voto statistico è assegnabile (senza voto = non eleggibile)."""
    threshold = coerce_minutes_threshold(minutes_threshold)

    if minutes is None or minutes <= 0:
        if has_relevant_event:
            return EligibilityDecision(True, "relevant_event_zero_minutes")
        if entered_in_stoppage:
            return EligibilityDecision(False, "stoppage_entry_no_relevant_event")
        return EligibilityDecision(False, "no_minutes")

    if minutes >= threshold:
        return EligibilityDecision(True, "minutes_threshold")

    if goalkeeper_starter_always_eligible and role == "P" and not substitute:
        return EligibilityDecision(True, "goalkeeper_starter")

    if has_relevant_event:
        return EligibilityDecision(True, "relevant_event_under_threshold")

    if entered_in_stoppage:
        return EligibilityDecision(False, "stoppage_entry_no_relevant_event")

    return EligibilityDecision(False, "under_threshold_no_relevant_event")


def _as_optional_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
