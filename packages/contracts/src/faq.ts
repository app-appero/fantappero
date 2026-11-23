/**
 * «Domande frequenti» per i fantallenatori (release 1.4) — fonte unica per sito e app.
 *
 * Il testo viene dal capitolo 5 di `docs/operations/regolamento_turni_calendario.md` e dalla
 * vista «Domande frequenti» del canvas approvato da Rosario (22/11): stesse domande, stesso
 * ordine, stesse parole. «Cos'è la regola del 75%?» riassume il capitolo 2 dello stesso file.
 * Le risposte descrivono il comportamento del codice: se una regola cambia, aggiorna insieme
 * il regolamento e questo file.
 */

/** Una domanda con la sua risposta, divisa in paragrafi brevi. */
export type FaqItem = {
  /** Identificativo stabile: serve per il link diretto alla domanda (`?domanda=<id>`). */
  id: string;
  question: string;
  answer: readonly string[];
};

/** Un gruppo di domande sullo stesso argomento (turni, calendario, ruoli, formazione). */
export type FaqGroup = {
  id: string;
  title: string;
  items: readonly FaqItem[];
};

export const FAQ_TITLE = "Domande frequenti";

export const FAQ_INTRO =
  "Le risposte alle domande più comuni su turni, calendario, ruoli e formazione. " +
  "Tocca una domanda per aprirla.";

/** Pagina del sito; nel link diretto il parametro `domanda` apre una sola risposta. */
export const FAQ_PATH = "/domande-frequenti";
export const FAQ_QUESTION_PARAM = "domanda";

export const FAQ_GROUPS: readonly FaqGroup[] = [
  {
    id: "turni",
    title: "Turni",
    items: [
      {
        id: "turno-saltato",
        question: "Perché un turno è «saltato»?",
        answer: [
          "Perché in quella finestra almeno una squadra della lega non avrebbe potuto schierare almeno 9 titolari con giocatori che giocano davvero, per esempio durante una sosta di uno dei campionati. Per non svantaggiare nessuno, il turno non conta per nessuno.",
        ],
      },
      {
        id: "regola-75",
        question: "Cos'è la regola del 75%?",
        answer: [
          "Un turno si gioca solo se ogni squadra della lega può coprire almeno il 75% degli 11 posti della formazione, cioè 9 su 11, con giocatori la cui squadra vera gioca in quel turno. Il sistema prova tutti i moduli e tiene quello che copre più posti.",
          "Qui «titolari» vuol dire gli 11 posti della formazione, non i titolari veri annunciati prima delle partite. Conta solo che la squadra vera del giocatore abbia una partita in quel turno, cosa che si sa settimane prima.",
          "La percentuale la sceglie la lega, da 50% a 100%. La trovi nella home della lega, in «Regolamento», alla voce «Titolari minimi per il turno».",
        ],
      },
      {
        id: "titolare-non-gioca",
        question: "Se un mio titolare non gioca, prendo 0?",
        answer: [
          "No: entra un giocatore della tua panchina, nell'ordine che hai scelto e rispettando il modulo, fino a 5 cambi. È il normale funzionamento del fantacalcio.",
        ],
      },
      {
        id: "campionati-diversi",
        question: "Ho tanti giocatori di campionati diversi: rischio?",
        answer: [
          "Se in un turno gioca solo un campionato e tu non hai almeno 9 titolari possibili in quel campionato, il turno salta per tutti. Non prendi 0 da solo. Più la rosa è distribuita sui campionati della lega, meno turni saltano.",
        ],
      },
    ],
  },
  {
    id: "calendario",
    title: "Calendario",
    items: [
      {
        id: "calendario-cambia",
        question: "Il calendario cambierà?",
        answer: [
          "Solo le giornate future che diventano non giocabili, per partite rinviate o per cambi di rosa, si spostano. Le giornate con risultati non cambiano mai.",
        ],
      },
    ],
  },
  {
    id: "ruoli",
    title: "Ruoli",
    items: [
      {
        id: "cambio-ruolo",
        question: "Perché un mio giocatore ha cambiato ruolo?",
        answer: [
          "Non dovrebbe più succedere: dal 22/11 i ruoli del listone sono fissi per la stagione. Se l'admin della lega ha forzato un ruolo, il cambio vale dal turno successivo.",
        ],
      },
      {
        id: "esubero",
        question: "Ho un giocatore «in esubero»: cosa faccio?",
        answer: [
          "Hai più giocatori di quelli ammessi in quel ruolo. Puoi svincolarne uno o scambiarlo. Finché la rosa non torna in regola, quel giocatore non si può schierare.",
        ],
      },
    ],
  },
  {
    id: "formazione",
    title: "Formazione",
    items: [
      {
        id: "blocco-formazione",
        question: "Quando si blocca la formazione?",
        answer: [
          "Ogni giocatore si blocca poco prima della sua partita, di solito 15 minuti. Gli altri si possono ancora cambiare fino alla loro partita.",
        ],
      },
    ],
  },
];

/** Tutte le domande, nell'ordine della pagina. */
export function faqItems(groups: readonly FaqGroup[] = FAQ_GROUPS): FaqItem[] {
  return groups.flatMap((group) => group.items);
}

/** La domanda con quell'id (link diretto), o `null` se non esiste. */
export function findFaqItem(
  id: string | null | undefined,
  groups: readonly FaqGroup[] = FAQ_GROUPS,
): FaqItem | null {
  const wanted = (id ?? "").trim();
  if (!wanted) {
    return null;
  }
  return faqItems(groups).find((item) => item.id === wanted) ?? null;
}

/** Apre la domanda se è chiusa e la chiude se è aperta; le altre restano come sono. */
export function toggleFaqItem(openIds: readonly string[], id: string): string[] {
  return openIds.includes(id) ? openIds.filter((openId) => openId !== id) : [...openIds, id];
}

/** Link diretto a una domanda della pagina del sito. */
export function faqQuestionHref(id: string): string {
  return `${FAQ_PATH}?${FAQ_QUESTION_PARAM}=${encodeURIComponent(id)}`;
}
