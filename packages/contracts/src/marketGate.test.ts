import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
  isMarketActive,
  leagueNotFullMessage,
  marketNotFullNotice,
  marketSwitchLocked,
} from "./marketGate.ts";

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
