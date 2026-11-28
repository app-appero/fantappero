import assert from "node:assert/strict";
import test from "node:test";
import {
  REOPEN_GRACE_MS,
  beginExplicitOpen,
  claimAutoOpen,
  claimExplicitOpen,
  markReplacementPromptShown,
  replacementPromptShown,
  resetReplacementPromptMemory,
  wantsReplacementSheet,
} from "./tradeReplacementPrompt.ts";

test("1.5: la scelta del sostituto si apre da sola una volta per sessione, per lega", () => {
  resetReplacementPromptMemory();
  assert.equal(replacementPromptShown("league-1"), false);
  markReplacementPromptShown("league-1");
  assert.equal(replacementPromptShown("league-1"), true);
  assert.equal(replacementPromptShown("league-2"), false);
  // Riavvio dell'app: si riapre.
  resetReplacementPromptMemory();
  assert.equal(replacementPromptShown("league-1"), false);
});

test("1.5: il link della notifica chiede di aprire la scelta", () => {
  assert.equal(wantsReplacementSheet({ sostituto: "1" }), true);
  assert.equal(wantsReplacementSheet({ sostituto: "0" }), false);
  assert.equal(wantsReplacementSheet({}), false);
  assert.equal(wantsReplacementSheet(undefined), false);
});

/**
 * Anomalia di Rosario (24/11): con la notifica di un'altra lega il foglio «Scegli il sostituto»
 * si apriva due volte e «Più tardi» andava toccato due volte. Aprono il foglio due cose quasi
 * insieme: l'apertura da sola al cambio lega (`claimAutoOpen`) e la richiesta della schermata
 * Rosa (`beginExplicitOpen` → `claimExplicitOpen`). Dopo «Più tardi» non deve riaprirsi nessuna.
 */
test("1.5, notifica di un'altra lega: apre prima la richiesta di Rosa, l'apertura da sola poi tace", () => {
  resetReplacementPromptMemory();
  const t0 = 1_000_000;
  // Cambio lega: partono insieme la lettura della Rosa (richiesta) e quella del provider (da sola).
  const token = beginExplicitOpen();
  assert.equal(claimExplicitOpen("lega-2", token, t0 + 120), true);
  // «Più tardi»; poi arriva la lettura più lenta del provider: non deve riaprire.
  assert.equal(claimAutoOpen("lega-2", t0 + 900), false);
  assert.equal(replacementPromptShown("lega-2"), true);
});

test("1.5, notifica di un'altra lega: apre prima da sola, la richiesta di Rosa arrivata dopo non riapre", () => {
  resetReplacementPromptMemory();
  const t0 = 1_000_000;
  const token = beginExplicitOpen();
  assert.equal(claimAutoOpen("lega-2", t0 + 100), true);
  // «Più tardi» toccato subito; la richiesta di Rosa risponde dopo e vede che il foglio si è già aperto.
  assert.equal(claimExplicitOpen("lega-2", token, t0 + 600), false);
});

test("1.5: una richiesta partita dopo l'apertura, ma entro pochi secondi, non riapre il foglio", () => {
  resetReplacementPromptMemory();
  const t0 = 1_000_000;
  assert.equal(claimAutoOpen("lega-2", t0), true);
  // Rosa si monta in ritardo e chiede solo ora: stesso evento, il foglio c'è già stato.
  const token = beginExplicitOpen();
  assert.equal(claimExplicitOpen("lega-2", token, t0 + REOPEN_GRACE_MS - 1), false);
});

test("1.5: un tocco nuovo sul link della notifica, dopo un po', riapre il foglio anche dopo «Più tardi»", () => {
  resetReplacementPromptMemory();
  const t0 = 1_000_000;
  assert.equal(claimAutoOpen("lega-2", t0), true);
  const token = beginExplicitOpen();
  assert.equal(claimExplicitOpen("lega-2", token, t0 + REOPEN_GRACE_MS), true);
  // E subito dopo la stessa richiesta non si ripete (nessuna doppia apertura per lo stesso tocco).
  assert.equal(claimExplicitOpen("lega-2", token, t0 + REOPEN_GRACE_MS + 1), false);
});

test("1.5: l'apertura da sola vale una volta per lega, anche dopo una richiesta in un'altra lega", () => {
  resetReplacementPromptMemory();
  assert.equal(claimAutoOpen("lega-1", 10), true);
  assert.equal(claimAutoOpen("lega-1", 20), false);
  const token = beginExplicitOpen();
  assert.equal(claimExplicitOpen("lega-2", token, 30), true);
  // Un'altra lega, mai mostrata: l'apertura da sola vale; per la lega 2 non riapre.
  assert.equal(claimAutoOpen("lega-3", 40), true);
  assert.equal(claimAutoOpen("lega-2", 50), false);
});
