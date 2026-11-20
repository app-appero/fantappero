import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
  isMarketActive,
  leagueNotFullMessage,
  leagueOccupancyLabel,
  marketNotFullNotice,
  marketSwitchLocked,
  pendingInvitesLabel,
} from "./marketGateNotice.ts";

describe("mercato e lega al completo nell'app (decisione del 20/11)", () => {
  it("il testo riporta iscritti e partecipanti previsti", () => {
    assert.equal(
      leagueNotFullMessage(5, 8),
      "Il mercato si apre quando la lega è al completo (5/8).",
    );
  });

  it("il banner c'è solo a lega incompleta", () => {
    assert.equal(
      marketNotFullNotice({ marketOpen: false, leagueFull: false, memberCount: 5, participantCount: 8 }),
      "Il mercato si apre quando la lega è al completo (5/8).",
    );
    assert.equal(
      marketNotFullNotice({ marketOpen: true, leagueFull: true, memberCount: 8, participantCount: 8 }),
      null,
    );
    // Risposta senza i campi nuovi (backend più vecchio): nessun banner.
    assert.equal(marketNotFullNotice({ marketOpen: true }), null);
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
    assert.equal(leagueNotFullMessage(3, 4, 0), "Il mercato si apre quando la lega è al completo (3/4).");
    assert.equal(leagueOccupancyLabel(3, 4, 1), "3/4 · 1 invito in attesa");
    assert.equal(leagueOccupancyLabel(3, 4), "3/4");
    assert.equal(pendingInvitesLabel(2), "2 inviti in attesa");
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
  });

  it("l'interruttore spento non si accende a lega incompleta, quello acceso si spegne", () => {
    assert.equal(marketSwitchLocked({ marketOpen: false, leagueFull: false }), true);
    assert.equal(marketSwitchLocked({ marketOpen: true, leagueFull: false }), false);
    assert.equal(marketSwitchLocked({ marketOpen: false, leagueFull: true }), false);
  });

  it("rosa, aste e scambi del partecipante vogliono interruttore acceso e lega al completo", () => {
    assert.equal(isMarketActive({ marketOpen: true, leagueFull: true }), true);
    assert.equal(isMarketActive({ marketOpen: true, leagueFull: false }), false);
    assert.equal(isMarketActive({ marketOpen: false, leagueFull: true }), false);
    assert.equal(isMarketActive({ marketOpen: true }), true);
  });
});
