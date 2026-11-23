/**
 * «Domande frequenti» (1.4): cosa legge il lettore di schermo su ogni domanda.
 *
 * Solo logica pura e import di tipo: gira nei test `node:test` senza il bundle di
 * React Native (il testo è in `@fantappero/contracts`, lo stesso del sito).
 */
import type { FaqItem } from "@fantappero/contracts";

export type FaqItemAccessibility = {
  label: string;
  hint: string;
};

/** La domanda, e cosa succede toccandola: apre o chiude la risposta. */
export function faqItemAccessibility(
  item: Pick<FaqItem, "question">,
  expanded: boolean,
): FaqItemAccessibility {
  return {
    label: item.question,
    hint: expanded ? "Tocca per chiudere la risposta" : "Tocca per aprire la risposta",
  };
}
