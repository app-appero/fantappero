"""Note del registro crediti mostrate a web e app (QA 21→22/11)."""

from __future__ import annotations

from uuid import uuid4

import pytest

from database.enums import CreditLedgerReason
from fantasy_teams.ledger import ledger_note_for_display
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
            "Svincolo L. JovanoviÄ\u0087 (voluntary, 50%)",
            "Svincolo L. Jovanović (voluntary, 50%)",
        ),
    ],
)
def test_system_notes_with_broken_names_are_shown_repaired(
    reason: CreditLedgerReason, stored: str, shown: str
) -> None:
    assert ledger_note_for_display(_entry(reason, stored)) == shown


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
