import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
  MODULE_CHANGE_FALLBACK_MESSAGE,
  moduleChangeFallbackNotice,
  moduleChangeRoute,
} from "./moduleChange.ts";

describe("moduleChangeRoute", () => {
  const base = { lockedCount: 0, lineupComplete: true, editable: true, hasSession: true };

  it("senza bloccati chiede al server la formazione migliore sul nuovo modulo", () => {
    assert.equal(moduleChangeRoute(base), "best");
    assert.equal(moduleChangeRoute({ ...base, lineupComplete: false }), "best");
  });

  it("con formazione completa e bloccati tiene i bloccati al loro posto, senza server", () => {
    assert.equal(moduleChangeRoute({ ...base, lockedCount: 2 }), "planned");
    assert.equal(moduleChangeRoute({ ...base, lockedCount: 2, hasSession: false }), "planned");
  });

  it("con bloccati ma formazione incompleta chiede comunque la migliore", () => {
    assert.equal(moduleChangeRoute({ ...base, lockedCount: 1, lineupComplete: false }), "best");
  });

  it("offline o turno non modificabile: solo i compatibili", () => {
    assert.equal(moduleChangeRoute({ ...base, hasSession: false }), "compatible");
    assert.equal(moduleChangeRoute({ ...base, editable: false }), "compatible");
    assert.equal(moduleChangeRoute({ ...base, lockedCount: 1, lineupComplete: false, editable: false }), "compatible");
  });
});

describe("moduleChangeFallbackNotice", () => {
  const apiError = (code: string) => Object.assign(new Error("errore"), { code, status: 422 });

  it("con pochi disponibili mostra il messaggio del server (cosa manca per ruolo)", () => {
    const message =
      "Formazione migliore non applicata: per il modulo 4-4-2 mancano calciatori disponibili (1 difensore).";
    const error = Object.assign(new Error(message), { code: "ai_lineup_incomplete", status: 400 });
    assert.equal(moduleChangeFallbackNotice(error), message);
  });

  it("tace sugli altri rifiuti previsti: rosa non validata e turno non modificabile", () => {
    for (const code of [
      "roster_not_validated",
      "turn_not_open",
      "turn_skipped",
      "turn_modification_closed",
    ]) {
      assert.equal(moduleChangeFallbackNotice(apiError(code)), null, code);
    }
  });

  it("mostra il messaggio breve sugli errori veri", () => {
    assert.equal(moduleChangeFallbackNotice(apiError("network_error")), MODULE_CHANGE_FALLBACK_MESSAGE);
    assert.equal(moduleChangeFallbackNotice(apiError("internal_error")), MODULE_CHANGE_FALLBACK_MESSAGE);
    assert.equal(moduleChangeFallbackNotice(new TypeError("Failed to fetch")), MODULE_CHANGE_FALLBACK_MESSAGE);
    assert.equal(moduleChangeFallbackNotice(undefined), MODULE_CHANGE_FALLBACK_MESSAGE);
  });
});
