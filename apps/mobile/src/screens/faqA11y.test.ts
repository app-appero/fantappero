import assert from "node:assert/strict";
import { describe, it } from "node:test";
// Lo stesso testo che l'app prende da `@fantappero/contracts` (qui dal sorgente).
import {
  FAQ_GROUPS,
  faqItems,
  findFaqItem,
  toggleFaqItem,
} from "../../../../packages/contracts/src/faq.ts";
import { faqItemAccessibility } from "./faqA11y.ts";

describe("Domande frequenti 1.4 — app", () => {
  it("il lettore di schermo legge la domanda e dice se il tocco apre o chiude la risposta", () => {
    const item = findFaqItem("blocco-formazione");
    assert.ok(item);
    assert.deepEqual(faqItemAccessibility(item, false), {
      label: "Quando si blocca la formazione?",
      hint: "Tocca per aprire la risposta",
    });
    assert.equal(faqItemAccessibility(item, true).hint, "Tocca per chiudere la risposta");
  });

  it("usa gli stessi gruppi e le stesse domande del sito", () => {
    assert.deepEqual(
      FAQ_GROUPS.map((group) => group.title),
      ["Turni", "Calendario", "Ruoli", "Formazione"],
    );
    assert.equal(faqItems().length, 8);
    assert.ok(faqItems().every((item) => item.answer.length > 0));
  });

  it("un tocco apre una risposta, un altro la richiude; le altre restano aperte", () => {
    const opened = toggleFaqItem(toggleFaqItem([], "turno-saltato"), "esubero");
    assert.deepEqual(opened, ["turno-saltato", "esubero"]);
    assert.deepEqual(toggleFaqItem(opened, "turno-saltato"), ["esubero"]);
  });
});
