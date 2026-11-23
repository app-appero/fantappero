import assert from "node:assert/strict";
import { test } from "node:test";

import {
  FAQ_GROUPS,
  FAQ_HELP,
  FAQ_HELP_ALL_LABEL,
  FAQ_HELP_CLOSE_LABEL,
  FAQ_INTRO,
  FAQ_PATH,
  FAQ_TITLE,
  faqHelpItem,
  faqHelpLabel,
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

test("ogni numero che la lega può cambiare dice che è la regola standard e rimanda a «Regolamento»", () => {
  const answer = (id: string) => findFaqItem(id)?.answer.join(" ") ?? "";
  // Soglia dei titolari (50%-100% per lega): 9 su 11 vale solo con il 75% standard.
  assert.match(
    answer("turno-saltato"),
    /almeno 9 titolari \(è la regola standard: la tua lega può averne scelta un'altra, la trovi in «Regolamento»\)/,
  );
  assert.match(
    answer("campionati-diversi"),
    /almeno 9 titolari possibili in quel campionato \(è la regola standard: la tua lega può averne scelta un'altra, la trovi in «Regolamento»\)/,
  );
  assert.match(answer("regola-75"), /Il 75% è la regola standard: la percentuale la sceglie la lega/);
  // Turno saltato: due motivi (Rosario 23/11), anche il minimo di partite della lega (25 standard).
  assert.match(answer("turno-saltato"), /Per uno di questi due motivi/);
  assert.match(
    answer("turno-saltato"),
    /25 con la regola standard \(la tua lega può averne scelto un altro, lo trovi in «Regolamento» alla voce «Partite minime per turno»\)/,
  );
  assert.match(answer("turno-saltato"), /«20 partite eleggibili su 25»/);
  // Cambi automatici (0-5 per lega) e minuti del blocco (0-60 per lega).
  assert.match(
    answer("titolare-non-gioca"),
    /fino a 5 cambi \(è la regola standard: la tua lega può averne scelti altri, li trovi in «Regolamento»\)/,
  );
  assert.match(
    answer("blocco-formazione"),
    /di solito 15 minuti \(è la regola standard: la tua lega può averne scelti altri, li trovi in «Regolamento»\)/,
  );
  // Nessun altro numero di regola senza la nota: le risposte senza numeri restano come sono.
  const withNote = new Set(["turno-saltato", "regola-75", "titolare-non-gioca", "campionati-diversi", "blocco-formazione"]);
  for (const item of faqItems()) {
    const text = item.answer.join(" ");
    if (withNote.has(item.id)) {
      assert.match(text, /regola standard/, `manca la nota sulla regola standard: ${item.id}`);
    } else {
      assert.doesNotMatch(text, /regola standard/, `nota sulla regola standard di troppo: ${item.id}`);
      assert.doesNotMatch(text, /\b\d+ (titolari|cambi|minuti)\b|\d+%/, `numero di regola senza nota: ${item.id}`);
    }
  }
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

test("i «?» aprono domande che esistono, con un nome accessibile senza virgolette", () => {
  assert.deepEqual(FAQ_HELP, {
    skippedTurn: "turno-saltato",
    surplus: "esubero",
    lineupLock: "blocco-formazione",
  });
  for (const id of Object.values(FAQ_HELP)) {
    assert.equal(faqHelpItem(id).id, id);
  }
  assert.equal(faqHelpLabel(faqHelpItem(FAQ_HELP.skippedTurn)), "Perché un turno è saltato?");
  assert.equal(faqHelpLabel(faqHelpItem(FAQ_HELP.surplus)), "Ho un giocatore in esubero: cosa faccio?");
  assert.equal(faqHelpLabel(faqHelpItem(FAQ_HELP.lineupLock)), "Quando si blocca la formazione?");
  assert.equal(FAQ_HELP_ALL_LABEL, "Tutte le domande frequenti");
  assert.equal(FAQ_HELP_CLOSE_LABEL, "Ho capito");
  assert.equal(faqQuestionHref(FAQ_HELP.surplus), "/domande-frequenti?domanda=esubero");
  assert.throws(() => faqHelpItem("non-esiste" as never), /sconosciuta/);
});
