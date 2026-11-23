/**
 * Elenco delle leghe del selettore: si rilegge quando l'utente tira una pagina per aggiornarla
 * e quando l'app torna in primo piano. Prima si leggeva solo all'avvio e dopo crea/unisciti/
 * elimina dall'app: una lega creata dal sito o dall'API compariva solo riavviando l'app
 * (corsa M3, 22/11).
 *
 * `PageContainer` (unico punto di ogni «tira per aggiornare») chiede l'aggiornamento; la
 * sessione (`DemoSessionContext`) ascolta e chiama `refreshMemberships`.
 *
 * Solo logica pura e import di tipo: gira nei test `node:test`.
 */
import type { LeagueSummary } from "@fantappero/contracts";

type Listener = () => void;

const listeners = new Set<Listener>();

export function requestLeagueListRefresh(): void {
  for (const listener of listeners) {
    listener();
  }
}

export function subscribeLeagueListRefresh(listener: Listener): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

/**
 * Stesso elenco (stesse leghe nello stesso ordine, con nome, ruolo, stato e mercato uguali):
 * la sessione tiene l'array di prima e non ridisegna l'app per un aggiornamento senza novità.
 */
export function sameLeagueList(
  current: readonly LeagueSummary[],
  next: readonly LeagueSummary[],
): boolean {
  if (current.length !== next.length) {
    return false;
  }
  return current.every((league, index) => {
    const other = next[index];
    return (
      other !== undefined &&
      league.id === other.id &&
      league.name === other.name &&
      league.role === other.role &&
      league.state === other.state &&
      league.marketOpen === other.marketOpen
    );
  });
}
