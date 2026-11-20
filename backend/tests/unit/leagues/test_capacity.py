"""Lega al completo (decisione del 20/11/2026): il conto che apre il mercato."""

from __future__ import annotations

from leagues.capacity import LeagueOccupancy, league_not_full_message


def test_league_is_full_only_when_every_seat_is_taken() -> None:
    assert LeagueOccupancy(members=8, participants=8).is_full is True
    assert LeagueOccupancy(members=7, participants=8).is_full is False
    assert LeagueOccupancy(members=1, participants=4).is_full is False
    # Senza regolamento non c'è un numero di posti da riempire.
    assert LeagueOccupancy(members=4, participants=None).is_full is False


def test_league_not_full_message_reports_members_and_participants() -> None:
    assert league_not_full_message(LeagueOccupancy(members=5, participants=8)) == (
        "Il mercato si apre quando la lega è al completo (5/8 partecipanti)."
    )
