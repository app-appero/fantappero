"""Note del registro crediti mostrate a web e app (QA 21→22/11)."""

from __future__ import annotations

from uuid import uuid4

import pytest

from database.enums import CreditLedgerReason, MarketReleaseReason
from fantasy_teams.ledger import ledger_note_for_display, release_refund_note
from fantasy_teams.models import CreditLedgerEntry


def _entry(
    reason: CreditLedgerReason, note: str | None, transaction_id: str = "tx"
) -> CreditLedgerEntry:
    return CreditLedgerEntry(
        account_id=uuid4(),
        amount=-5,
        reason=reason,
        transaction_id=transaction_id,
        balance_after=995,
        note=note,
    )


@pytest.mark.parametrize(
    ("reason", "stored", "shown"),
    [
        (
            CreditLedgerReason.ROSTER_PURCHASE,
            "Assegnazione L. JovanoviÄ\u0087",
            "Assegnazione L. Jovanović",
        ),
        (CreditLedgerReason.ROSTER_PURCHASE, "Acquisto L. JovanoviÄ‡", "Acquisto L. Jovanović"),
        (CreditLedgerReason.ROSTER_PURCHASE, "Acquisto D. O&apos;Shea", "Acquisto D. O'Shea"),
        (CreditLedgerReason.ROSTER_PURCHASE, "Acquisto N. Kovač \u008d", "Acquisto N. Kovač"),
        (
            CreditLedgerReason.ROSTER_RELEASE_REFUND,
            "Rimborso D. O&#039;Shea",
            "Rimborso D. O'Shea",
        ),
        (
            CreditLedgerReason.MARKET_RELEASE_REFUND,
            "Svincolo L. JovanoviÄ\u0087 (volontario, 50%)",
            "Svincolo L. Jovanović (volontario, 50%)",
        ),
        # Salvata prima del 24/11: nome rovinato e causa in inglese, si mostra in italiano.
        (
            CreditLedgerReason.MARKET_RELEASE_REFUND,
            "Svincolo L. JovanoviÄ\u0087 (voluntary, 50%)",
            "Svincolo L. Jovanović (volontario, 50%)",
        ),
    ],
)
def test_system_notes_with_broken_names_are_shown_repaired(
    reason: CreditLedgerReason, stored: str, shown: str
) -> None:
    assert ledger_note_for_display(_entry(reason, stored)) == shown


@pytest.mark.parametrize(
    ("reason", "percent", "note"),
    [
        (MarketReleaseReason.VOLUNTARY, 50, "Svincolo D. O'Shea (volontario, 50%)"),
        (
            MarketReleaseReason.LEAGUE_EXIT,
            100,
            "Svincolo D. O'Shea (uscita dai cinque campionati, 100%)",
        ),
    ],
)
def test_release_refund_note_is_in_italian(
    reason: MarketReleaseReason, percent: int, note: str
) -> None:
    """24/11: la causa nella nota del rimborso è in italiano (prima «voluntary», «league_exit»)."""
    assert release_refund_note("D. O'Shea", reason, percent) == note
    shown = ledger_note_for_display(_entry(CreditLedgerReason.MARKET_RELEASE_REFUND, note))
    assert shown == note


@pytest.mark.parametrize(
    ("stored", "shown"),
    [
        ("Svincolo Rossi (voluntary, 50%)", "Svincolo Rossi (volontario, 50%)"),
        ("Svincolo Rossi (voluntary, 30%)", "Svincolo Rossi (volontario, 30%)"),
        (
            "Svincolo Rossi (league_exit, 100%)",
            "Svincolo Rossi (uscita dai cinque campionati, 100%)",
        ),
    ],
)
def test_release_refund_notes_stored_before_the_change_are_shown_in_italian(
    stored: str, shown: str
) -> None:
    """Il registro non si riscrive: i rimborsi salvati prima del 24/11 si traducono alla lettura."""
    entry = _entry(CreditLedgerReason.MARKET_RELEASE_REFUND, stored)
    assert ledger_note_for_display(entry) == shown
    assert entry.note == stored


def test_only_release_refund_notes_are_translated() -> None:
    """La stessa frase con un'altra causale (o scritta dall'amministratore) resta com'è."""
    note = "Svincolo Rossi (voluntary, 50%)"
    for reason in (CreditLedgerReason.ROSTER_RELEASE_REFUND, CreditLedgerReason.ADMIN_ADJUSTMENT):
        assert ledger_note_for_display(_entry(reason, note)) == note


def test_clean_notes_and_missing_notes_are_unchanged() -> None:
    clean = "Rettifica prezzo A. Dembélé"
    assert ledger_note_for_display(_entry(CreditLedgerReason.ROSTER_PURCHASE, clean)) == clean
    assert ledger_note_for_display(_entry(CreditLedgerReason.ROSTER_PURCHASE, None)) is None


def test_admin_free_note_is_shown_as_written() -> None:
    """La nota libera della rettifica manuale è testo dell'amministratore: non si tocca."""
    note = "Bonus R&amp;D per JovanoviÄ\u0087 \u008d"
    assert ledger_note_for_display(_entry(CreditLedgerReason.ADMIN_ADJUSTMENT, note)) == note


def test_old_live_auction_note_still_shows_the_live_label() -> None:
    entry = _entry(
        CreditLedgerReason.MARKET_AUCTION_WIN,
        "Assegnazione da asta a buste",
        transaction_id="market-live:lot:team:bid",
    )
    assert ledger_note_for_display(entry) == "Assegnazione da asta a rilanci"
