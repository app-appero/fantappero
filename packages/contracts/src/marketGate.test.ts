import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
  isMarketActive,
  leagueNotFullMessage,
  leagueOccupancyLabel,
  MARKET_STATUS_BADGE_LABEL,
  marketBlockedNotice,
  marketClosedTitle,
  marketNotFullNotice,
  marketRoundInProgress,
  marketStatusBadge,
  marketSwitchLocked,
  pendingInvitesLabel,
} from "./marketGate.ts";

describe("mercato a turno in corso (decisione di Rosario del 21/11)", () => {
  const roundGate = {
    marketOpen: true,
    leagueFull: true,
    marketBlockedReason: "round_in_progress" as const,
  };

  it("non si legge più «Mercato aperto»: «Mercato fermo: turno in corso»", () => {
    assert.equal(marketStatusBadge(roundGate), "round_in_progress");
    assert.equal(
      `Mercato ${MARKET_STATUS_BADGE_LABEL[marketStatusBadge(roundGate)]}`,
      "Mercato fermo: turno in corso",
    );
    // Anche a interruttore spento il turno in corso blocca gli scambi.
    assert.equal(marketStatusBadge({ ...roundGate, marketOpen: false }), "round_in_progress");
    assert.equal(marketStatusBadge({ marketOpen: true, leagueFull: true }), "open");
    assert.equal(marketStatusBadge({ marketOpen: false, leagueFull: true }), "closed");
    assert.equal(
      marketStatusBadge({ marketOpen: true, leagueFull: false, marketBlockedReason: "league_not_full" }),
      "closed",
    );
  });

  it("il mercato del partecipante si ferma e il motivo resta visibile", () => {
    assert.equal(marketRoundInProgress(roundGate), true);
    assert.equal(isMarketActive(roundGate), false);
    assert.equal(
      marketBlockedNotice(roundGate),
      "Rosa, aste e scambi sono fermi finché il turno non è calcolato.",
    );
    assert.equal(marketClosedTitle(roundGate), "Mercato fermo: turno in corso");
    assert.equal(marketClosedTitle({ marketOpen: false, leagueFull: true }), "Mercato chiuso");
    assert.equal(marketBlockedNotice({ marketOpen: true, leagueFull: true }), null);
    assert.equal(
      marketBlockedNotice({ marketOpen: false, leagueFull: false, memberCount: 3, participantCount: 4 }),
      "Il mercato si apre quando la lega è al completo (3/4).",
    );
  });
});

describe("mercato e lega al completo (decisione del 20/11)", () => {
  it("il testo riporta iscritti e partecipanti previsti", () => {
    assert.equal(
      leagueNotFullMessage(5, 8),
      "Il mercato si apre quando la lega è al completo (5/8).",
    );
  });

  it("a lega incompleta l'avviso c'è, a lega al completo no", () => {
    assert.equal(
      marketNotFullNotice({ marketOpen: false, leagueFull: false, memberCount: 5, participantCount: 8 }),
      "Il mercato si apre quando la lega è al completo (5/8).",
    );
    assert.equal(
      marketNotFullNotice({ marketOpen: false, leagueFull: true, memberCount: 8, participantCount: 8 }),
      null,
    );
    // Una risposta senza `leagueFull` (backend più vecchio, demo) non blocca nulla.
    assert.equal(marketNotFullNotice({ marketOpen: true }), null);
    assert.equal(marketNotFullNotice(null), null);
  });

  it("accanto al conto gli inviti in attesa, solo se ci sono (Rosario, 20/11)", () => {
    assert.equal(
      marketNotFullNotice({
        marketOpen: false,
        leagueFull: false,
        memberCount: 3,
        participantCount: 4,
        pendingInviteCount: 1,
      }),
      "Il mercato si apre quando la lega è al completo (3/4 · 1 invito in attesa).",
    );
    assert.equal(
      leagueNotFullMessage(2, 4, 2),
      "Il mercato si apre quando la lega è al completo (2/4 · 2 inviti in attesa).",
    );
    assert.equal(
      marketNotFullNotice({
        marketOpen: false,
        leagueFull: false,
        memberCount: 3,
        participantCount: 4,
        pendingInviteCount: 0,
      }),
      "Il mercato si apre quando la lega è al completo (3/4).",
    );
    assert.equal(leagueOccupancyLabel(3, 4, 1), "3/4 · 1 invito in attesa");
    assert.equal(leagueOccupancyLabel(3, 4), "3/4");
    assert.equal(leagueOccupancyLabel(3, 4, null), "3/4");
    assert.equal(pendingInvitesLabel(1), "1 invito in attesa");
    assert.equal(pendingInvitesLabel(3), "3 inviti in attesa");
    // Gli inviti non rendono la lega al completo: decide solo `leagueFull` (gli iscritti).
    assert.equal(
      marketNotFullNotice({
        marketOpen: false,
        leagueFull: true,
        memberCount: 4,
        participantCount: 4,
        pendingInviteCount: 1,
      }),
      null,
    );
    assert.equal(
      marketSwitchLocked({ marketOpen: false, leagueFull: false, pendingInviteCount: 1 }),
      true,
    );
  });

  it("l'interruttore non si accende a lega incompleta ma si spegne sempre", () => {
    assert.equal(marketSwitchLocked({ marketOpen: false, leagueFull: false }), true);
    // Lega esistente con l'interruttore già acceso: si può spegnere.
    assert.equal(marketSwitchLocked({ marketOpen: true, leagueFull: false }), false);
    assert.equal(marketSwitchLocked({ marketOpen: false, leagueFull: true }), false);
    assert.equal(marketSwitchLocked({ marketOpen: false }), false);
  });

  it("il mercato del partecipante richiede interruttore acceso e lega al completo", () => {
    assert.equal(isMarketActive({ marketOpen: true, leagueFull: true }), true);
    assert.equal(isMarketActive({ marketOpen: true, leagueFull: false }), false);
    assert.equal(isMarketActive({ marketOpen: false, leagueFull: true }), false);
    assert.equal(isMarketActive({ marketOpen: true }), true);
  });
});
