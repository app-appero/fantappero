import { useEffect, useRef, useState, type Dispatch, type SetStateAction } from "react";
import { syncPriceDraft } from "./pricePrefill";

/**
 * Campo prezzo che parte dal prezzo proposto (`suggestion`, dal Valore o il default di oggi)
 * e lo segue quando cambia, finché l'utente non scrive un'altra cifra (`syncPriceDraft`).
 */
export function useSuggestedDraft(suggestion: string): [string, Dispatch<SetStateAction<string>>] {
  const [draft, setDraft] = useState(suggestion);
  const previous = useRef(suggestion);
  useEffect(() => {
    const previousSuggestion = previous.current;
    if (previousSuggestion === suggestion) {
      return;
    }
    previous.current = suggestion;
    setDraft((current) => syncPriceDraft({ draft: current, previousSuggestion, suggestion }));
  }, [suggestion]);
  return [draft, setDraft];
}
