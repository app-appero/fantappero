"""Lega al completo (decisione del 20/11/2026): il conto che apre il mercato."""

from __future__ import annotations

from leagues.capacity import LeagueOccupancy, league_not_full_message, pending_invites_label


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


def test_pending_invites_are_shown_next_to_the_count_but_do_not_fill_the_league() -> None:
    """Rosario, 20/11: gli inviti nominativi in attesa compaiono accanto al conto, solo se ci
    sono; la lega è al completo soltanto con gli iscritti."""
    one = LeagueOccupancy(members=3, participants=4, pending_invites=1)
    two = LeagueOccupancy(members=2, participants=4, pending_invites=2)
    assert one.is_full is False
    assert two.is_full is False
    assert LeagueOccupancy(members=4, participants=4, pending_invites=1).is_full is True
    assert league_not_full_message(one) == (
        "Il mercato si apre quando la lega è al completo (3/4 partecipanti · 1 invito in attesa)."
    )
    assert league_not_full_message(two) == (
        "Il mercato si apre quando la lega è al completo (2/4 partecipanti · 2 inviti in attesa)."
    )
    assert pending_invites_label(1) == "1 invito in attesa"
    assert pending_invites_label(2) == "2 inviti in attesa"
