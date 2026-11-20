import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
  isMarketActive,
  leagueNotFullMessage,
  marketNotFullNotice,
  marketSwitchLocked,
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
