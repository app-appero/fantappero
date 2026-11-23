import assert from "node:assert/strict";
import { test } from "node:test";

import {
  FAQ_HELP_GLYPH_SIZE,
  FAQ_HELP_LINK_HINT,
  FAQ_HELP_TOUCH_SIZE,
  faqHelpButtonAccessibility,
  faqHelpLinkTarget,
} from "./faqHelpA11y.ts";

// Le stesse domande di `@fantappero/contracts` (`FAQ_HELP`): turno saltato, esubero, blocco.
const SKIPPED = { id: "turno-saltato", question: "Perché un turno è «saltato»?" };
const SURPLUS = { id: "esubero", question: "Ho un giocatore «in esubero»: cosa faccio?" };
const LOCK = { id: "blocco-formazione", question: "Quando si blocca la formazione?" };

test("il «?» si chiama come la domanda, senza le virgolette «»", () => {
  assert.deepEqual(faqHelpButtonAccessibility(SKIPPED), {
    label: "Perché un turno è saltato?",
    hint: "Apre la risposta dal basso",
  });
  assert.equal(faqHelpButtonAccessibility(SURPLUS).label, "Ho un giocatore in esubero: cosa faccio?");
  assert.equal(faqHelpButtonAccessibility(LOCK).label, "Quando si blocca la formazione?");
});

test("«Tutte le domande frequenti» apre la schermata con la risposta del «?»", () => {
  assert.deepEqual(faqHelpLinkTarget(SKIPPED), { screen: "Faq", params: { domanda: "turno-saltato" } });
  assert.deepEqual(faqHelpLinkTarget(SURPLUS).params, { domanda: "esubero" });
  assert.match(FAQ_HELP_LINK_HINT, /Domande frequenti/);
});

test("l'area di tocco è di almeno 44px anche se il cerchio è più piccolo", () => {
  assert.ok(FAQ_HELP_TOUCH_SIZE >= 44);
  assert.ok(FAQ_HELP_GLYPH_SIZE < FAQ_HELP_TOUCH_SIZE);
});
