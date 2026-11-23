/**
 * Il piccolo «?» delle Domande frequenti (1.4): cosa legge il lettore di schermo e dove porta
 * il link «Tutte le domande frequenti» del foglio che si apre dal basso.
 *
 * Solo logica pura e import di tipo: gira nei test `node:test` senza il bundle di React Native
 * (il testo e gli id sono in `@fantappero/contracts`, gli stessi del sito).
 */
import type { FaqItem } from "@fantappero/contracts";

/** Lato minimo dell'area di tocco del «?» (il cerchio visibile è di 22px). */
export const FAQ_HELP_TOUCH_SIZE = 44;
/** Diametro del cerchio con il «?». */
export const FAQ_HELP_GLYPH_SIZE = 22;

export type FaqHelpButtonAccessibility = {
  label: string;
  hint: string;
};

/**
 * Il «?»: il nome è la domanda senza le virgolette «» (come sul sito, «Perché un turno è
 * saltato?»), il suggerimento dice che la risposta si apre sopra la pagina.
 */
export function faqHelpButtonAccessibility(item: Pick<FaqItem, "question">): FaqHelpButtonAccessibility {
  return {
    label: item.question.replace(/[«»]/g, "").replace(/\s+/g, " ").trim(),
    hint: "Apre la risposta dal basso",
  };
}

/** Il link in fondo al foglio: la schermata «Domande frequenti» con quella risposta aperta. */
export function faqHelpLinkTarget(item: Pick<FaqItem, "id">): { screen: "Faq"; params: { domanda: string } } {
  return { screen: "Faq", params: { domanda: item.id } };
}

/** Suggerimento del link «Tutte le domande frequenti». */
export const FAQ_HELP_LINK_HINT = "Apre «Domande frequenti» con questa risposta aperta";
