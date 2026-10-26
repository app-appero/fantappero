"""Dettaglio live di una partita del turno europeo (EP13-P04).

Sola lettura. Espone ciò che il backend ha già normalizzato — fixture, eventi
e formazioni ufficiali — senza mai contattare il provider dal client
(ADR-0001). Quando un dato manca, manca: non viene sostituito da un valore di
comodo.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from auth.exceptions import ValidationAuthError
from fantasy_turns.live_view import (
    PROVIDER_FEED_LABELS,
    FixtureFreshness,
    ProviderFeedState,
    RawTimelineEvent,
    build_timeline,
    fixture_feed_state,
    minute_label,
    substitution_minutes,
)
from fantasy_turns.models import FantasyRound, FantasyRoundFixture
from fantasy_turns.schemas import (
    FixtureLineupPlayerResponse,
    FixtureLineupResponse,
    FixtureLiveDetailResponse,
    FixtureTimelineEventResponse,
    FixtureUnavailablePlayerResponse,
)
from sports_data.catalog.models import Club
from sports_data.fixtures.models import Fixture, MatchEvent, OfficialLineup
from sports_data.predicted.read import (
    PredictedView,
    PredictedViewPlayer,
    PredictedViewSide,
    latest_predicted_view,
)
from sports_data.roster.models import Athlete


def get_fixture_live_detail(
    session: Session,
    *,
    league_id: UUID,
    round_id: UUID,
    fixture_id: UUID,
) -> FixtureLiveDetailResponse:
    """Dettaglio di una partita, vincolato al turno e alla lega richiesti."""
    fantasy_round = session.execute(
        select(FantasyRound).where(
            FantasyRound.id == round_id,
            FantasyRound.league_id == league_id,
        )
    ).scalar_one_or_none()
    if fantasy_round is None:
        raise ValidationAuthError("Turno non trovato.", code="turn_not_found")

    # La partita deve appartenere al turno: senza questo controllo un id
    # qualsiasi permetterebbe di leggere fixture fuori dalla lega.
    link = session.execute(
        select(FantasyRoundFixture).where(
            FantasyRoundFixture.round_id == round_id,
            FantasyRoundFixture.fixture_id == fixture_id,
            FantasyRoundFixture.excluded_at.is_(None),
        )
    ).scalar_one_or_none()
    if link is None:
        raise ValidationAuthError("Partita non trovata nel turno.", code="fixture_not_found")

    fixture = session.execute(
        select(Fixture)
        .where(Fixture.id == fixture_id)
        .options(
            selectinload(Fixture.home_club),
            selectinload(Fixture.away_club),
            selectinload(Fixture.sport_season),
        )
    ).scalar_one_or_none()
    if fixture is None:
        raise ValidationAuthError("Partita non trovata.", code="fixture_not_found")

    now = datetime.now(UTC)
    feed_state = fixture_feed_state(
        FixtureFreshness(status_short=fixture.status_short, updated_at=fixture.updated_at),
        now=now,
    )
    predicted = latest_predicted_view(session, fixture.id)
    raw_events = _raw_events(session, fixture_id=fixture.id)
    sub_out, sub_in = substitution_minutes(raw_events)
    home_lineup = _lineup_payload(
        session, fixture_id=fixture.id, club_id=fixture.home_club_id, sub_out=sub_out, sub_in=sub_in
    )
    away_lineup = _lineup_payload(
        session, fixture_id=fixture.id, club_id=fixture.away_club_id, sub_out=sub_out, sub_in=sub_in
    )
    if predicted is not None:
        if home_lineup is None and predicted.home is not None:
            home_lineup = _predicted_lineup_payload(
                predicted.home, fixture.home_club, sub_out=sub_out, sub_in=sub_in
            )
        if away_lineup is None and predicted.away is not None:
            away_lineup = _predicted_lineup_payload(
                predicted.away, fixture.away_club, sub_out=sub_out, sub_in=sub_in
            )

    return FixtureLiveDetailResponse(
        fixtureId=str(fixture.id),
        turnId=str(round_id),
        leagueId=str(league_id),
        providerId=fixture.provider_id,
        competitionName=_competition_name(fixture),
        homeClubId=str(fixture.home_club_id),
        awayClubId=str(fixture.away_club_id),
        homeClubName=fixture.home_club.name,
        awayClubName=fixture.away_club.name,
        homeClubLogoUrl=fixture.home_club.logo_url,
        awayClubLogoUrl=fixture.away_club.logo_url,
        homeGoals=fixture.home_goals,
        awayGoals=fixture.away_goals,
        statusShort=fixture.status_short,
        statusElapsed=fixture.status_elapsed,
        venueName=fixture.venue_name,
        venueCity=fixture.venue_city,
        referee=fixture.referee,
        kickoffAt=fixture.kickoff_at,
        updatedAt=fixture.updated_at,
        feedState=feed_state.value,
        feedStateLabel=PROVIDER_FEED_LABELS[feed_state],
        homeLineup=home_lineup,
        awayLineup=away_lineup,
        unavailablePlayers=_unavailable_payload(predicted, fixture),
        events=_timeline_payload(raw_events),
    )


def _competition_name(fixture: Fixture) -> str | None:
    if fixture.sport_season and fixture.sport_season.competition:
        return fixture.sport_season.competition.name
    return None


def _lineup_payload(
    session: Session,
    *,
    fixture_id: UUID,
    club_id: UUID,
    sub_out: dict[str, int],
    sub_in: dict[str, int],
) -> FixtureLineupResponse | None:
    lineup = session.execute(
        select(OfficialLineup)
        .where(
            OfficialLineup.fixture_id == fixture_id,
            OfficialLineup.club_id == club_id,
        )
        .options(
            selectinload(OfficialLineup.club),
            selectinload(OfficialLineup.entries),
        )
    ).scalar_one_or_none()
    if lineup is None:
        # Formazione ufficiale non ancora pubblicata: assente, non vuota.
        return None

    entries = sorted(lineup.entries, key=lambda row: (row.sort_order, row.athlete_provider_id))
    starters: list[FixtureLineupPlayerResponse] = []
    bench: list[FixtureLineupPlayerResponse] = []
    bench_order = 0
    for entry in entries:
        athlete = entry.athlete
        athlete_id = None if athlete is None else str(athlete.id)
        if not entry.is_starter:
            bench_order += 1
        payload = FixtureLineupPlayerResponse(
            athleteId=athlete_id,
            # Senza anagrafica collegata resta il numero provider: è ciò che
            # sappiamo davvero, meglio di un nome inventato.
            name=_athlete_name(athlete) or f"#{entry.athlete_provider_id}",
            shirtNumber=entry.shirt_number,
            position=entry.position_raw,
            grid=entry.grid,
            photoUrl=None if athlete is None else athlete.photo_url,
            benchOrder=None if entry.is_starter else bench_order,
            substitutedOutMinute=None if athlete_id is None else sub_out.get(athlete_id),
            substitutedInMinute=None if athlete_id is None else sub_in.get(athlete_id),
        )
        (starters if entry.is_starter else bench).append(payload)

    return FixtureLineupResponse(
        clubName=lineup.club.name,
        clubLogoUrl=lineup.club.logo_url,
        formation=lineup.formation,
        coachName=lineup.coach_name,
        starters=starters,
        bench=bench,
        lineupKind="official",
    )


def _predicted_player(
    row: PredictedViewPlayer,
    *,
    sub_out: dict[str, int],
    sub_in: dict[str, int],
) -> FixtureLineupPlayerResponse:
    return FixtureLineupPlayerResponse(
        athleteId=row.athlete_id,
        name=row.name,
        shirtNumber=row.shirt_number,
        grid=row.grid,
        role=row.role,
        benchOrder=row.bench_order,
        substitutedOutMinute=None if row.athlete_id is None else sub_out.get(row.athlete_id),
        substitutedInMinute=None if row.athlete_id is None else sub_in.get(row.athlete_id),
    )


def _predicted_lineup_payload(
    side: PredictedViewSide,
    club: Club,
    *,
    sub_out: dict[str, int],
    sub_in: dict[str, int],
) -> FixtureLineupResponse:
    return FixtureLineupResponse(
        clubName=club.name,
        clubLogoUrl=club.logo_url,
        formation=side.formation,
        coachName=side.coach_name,
        starters=[_predicted_player(row, sub_out=sub_out, sub_in=sub_in) for row in side.starters],
        bench=[_predicted_player(row, sub_out=sub_out, sub_in=sub_in) for row in side.bench],
        lineupKind="predicted",
        lineupNote=side.note,
    )


def _unavailable_payload(
    predicted: PredictedView | None,
    fixture: Fixture,
) -> list[FixtureUnavailablePlayerResponse]:
    if predicted is None:
        return []
    rows = []
    for player in predicted.unavailable:
        club_name = fixture.home_club.name if player.side == "home" else fixture.away_club.name
        rows.append(
            FixtureUnavailablePlayerResponse(
                athleteId=player.athlete_id,
                name=player.name,
                clubName=club_name,
                side=player.side,
                kind=player.kind,
                label=player.label,
                blocksSelection=player.blocks_selection,
            )
        )
    return rows


def _raw_events(
    session: Session,
    *,
    fixture_id: UUID,
) -> list[RawTimelineEvent]:
    rows = session.scalars(
        select(MatchEvent)
        .where(MatchEvent.fixture_id == fixture_id)
        .options(
            selectinload(MatchEvent.athlete),
            selectinload(MatchEvent.related_athlete),
            selectinload(MatchEvent.club),
        )
    ).all()

    return [
        RawTimelineEvent(
            id=str(row.id),
            minute_elapsed=row.minute_elapsed,
            minute_extra=row.minute_extra,
            event_type=row.event_type,
            event_detail=row.event_detail,
            scoring_kind=row.scoring_kind,
            club_id=None if row.club_id is None else str(row.club_id),
            club_name=None if row.club is None else row.club.name,
            athlete_id=None if row.athlete_id is None else str(row.athlete_id),
            athlete_name=_athlete_name(row.athlete),
            related_athlete_id=(
                None if row.related_athlete_id is None else str(row.related_athlete_id)
            ),
            related_athlete_name=_athlete_name(row.related_athlete),
            comments=row.comments,
            is_active=row.is_active,
            retracted_at=row.retracted_at,
            sources=tuple(row.sources) if isinstance(row.sources, list) else (),
        )
        for row in rows
    ]


def _timeline_payload(raw_events: list[RawTimelineEvent]) -> list[FixtureTimelineEventResponse]:
    timeline = build_timeline(raw_events)

    return [
        FixtureTimelineEventResponse(
            id=event.id,
            minuteElapsed=event.minute_elapsed,
            minuteExtra=event.minute_extra,
            minuteLabel=minute_label(event.minute_elapsed, event.minute_extra),
            eventType=event.event_type,
            eventDetail=event.event_detail,
            scoringKind=event.scoring_kind,
            clubId=event.club_id,
            clubName=event.club_name,
            athleteId=event.athlete_id,
            athleteName=event.athlete_name,
            relatedAthleteId=event.related_athlete_id,
            relatedAthleteName=event.related_athlete_name,
            comments=event.comments,
        )
        for event in timeline
    ]


def _athlete_name(athlete: Athlete | None) -> str | None:
    return None if athlete is None else athlete.canonical_name


__all__ = ["ProviderFeedState", "get_fixture_live_detail"]
