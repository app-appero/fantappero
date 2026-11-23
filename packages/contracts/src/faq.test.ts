import assert from "node:assert/strict";
import { test } from "node:test";

import {
  FAQ_GROUPS,
  FAQ_INTRO,
  FAQ_PATH,
  FAQ_TITLE,
  faqItems,
  faqQuestionHref,
  findFaqItem,
  toggleFaqItem,
} from "./faq.ts";

test("ogni domanda ha una domanda e una risposta non vuote", () => {
  for (const item of faqItems()) {
    assert.ok(item.question.trim().length > 0, `domanda vuota: ${item.id}`);
    assert.ok(item.question.trim().endsWith("?"), `la domanda non finisce con «?»: ${item.id}`);
    assert.ok(item.answer.length > 0, `risposta mancante: ${item.id}`);
    for (const paragraph of item.answer) {
      assert.ok(paragraph.trim().length > 0, `paragrafo vuoto nella risposta: ${item.id}`);
    }
  }
});

test("gli id di gruppi e domande sono unici e adatti a un link", () => {
  const groupIds = FAQ_GROUPS.map((group) => group.id);
  assert.equal(new Set(groupIds).size, groupIds.length);
  const itemIds = faqItems().map((item) => item.id);
  assert.equal(new Set(itemIds).size, itemIds.length);
  for (const id of [...groupIds, ...itemIds]) {
    assert.match(id, /^[a-z0-9]+(-[a-z0-9]+)*$/, `id non adatto a un link: ${id}`);
  }
});

test("ogni gruppo ha un titolo e almeno una domanda", () => {
  for (const group of FAQ_GROUPS) {
    assert.ok(group.title.trim().length > 0, `titolo vuoto: ${group.id}`);
    assert.ok(group.items.length > 0, `gruppo senza domande: ${group.id}`);
  }
});

test("le domande del canvas approvato, nello stesso ordine, più la regola del 75%", () => {
  assert.equal(FAQ_TITLE, "Domande frequenti");
  assert.match(FAQ_INTRO, /turni, calendario, ruoli e formazione/);
  assert.deepEqual(
    FAQ_GROUPS.map((group) => group.title),
    ["Turni", "Calendario", "Ruoli", "Formazione"],
  );
  assert.deepEqual(
    faqItems().map((item) => item.question),
    [
      "Perché un turno è «saltato»?",
      "Cos'è la regola del 75%?",
      "Se un mio titolare non gioca, prendo 0?",
      "Ho tanti giocatori di campionati diversi: rischio?",
      "Il calendario cambierà?",
      "Perché un mio giocatore ha cambiato ruolo?",
      "Ho un giocatore «in esubero»: cosa faccio?",
      "Quando si blocca la formazione?",
    ],
  );
});

test("le risposte riportano le regole in vigore (soglia 75%, 5 cambi, blocco di 15 minuti)", () => {
  const answer = (id: string) => findFaqItem(id)?.answer.join(" ") ?? "";
  assert.match(answer("regola-75"), /75% degli 11 posti della formazione, cioè 9 su 11/);
  assert.match(answer("regola-75"), /da 50% a 100%/);
  assert.match(answer("regola-75"), /«Titolari minimi per il turno»/);
  assert.match(answer("titolare-non-gioca"), /fino a 5 cambi/);
  assert.match(answer("blocco-formazione"), /di solito 15 minuti/);
  assert.match(answer("calendario-cambia"), /Le giornate con risultati non cambiano mai/);
  assert.match(answer("cambio-ruolo"), /ruoli del listone sono fissi per la stagione/);
  assert.match(answer("esubero"), /non si può schierare/);
});

test("findFaqItem trova la domanda del link diretto e ignora gli id sconosciuti", () => {
  assert.equal(findFaqItem("esubero")?.question, "Ho un giocatore «in esubero»: cosa faccio?");
  assert.equal(findFaqItem(" turno-saltato ")?.id, "turno-saltato");
  assert.equal(findFaqItem("non-esiste"), null);
  assert.equal(findFaqItem(""), null);
  assert.equal(findFaqItem(null), null);
});

test("toggleFaqItem apre e chiude una domanda senza toccare le altre", () => {
  assert.deepEqual(toggleFaqItem([], "esubero"), ["esubero"]);
  assert.deepEqual(toggleFaqItem(["turno-saltato"], "esubero"), ["turno-saltato", "esubero"]);
  assert.deepEqual(toggleFaqItem(["turno-saltato", "esubero"], "turno-saltato"), ["esubero"]);
});

test("faqQuestionHref porta alla pagina del sito con la domanda aperta", () => {
  assert.equal(FAQ_PATH, "/domande-frequenti");
  assert.equal(faqQuestionHref("turno-saltato"), "/domande-frequenti?domanda=turno-saltato");
});
