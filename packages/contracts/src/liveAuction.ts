/**
 * Logica pura condivisa web/mobile per l'asta a rilanci (EP08-09), sullo
 * stesso principio di ``pitch.ts``: qui vive UNA sola implementazione del
 * calcolo "rilancio minimo successivo" e del countdown, usata identica dalle
 * due app invece di essere duplicata.
 *
 * Solo per il feedback immediato in UI (es. disabilitare il pulsante di
 * rilancio sotto la soglia, mostrare il countdown): il server resta sempre
 * l'autorità finale su ogni scrittura — le controparti Python autoritative
 * sono ``backend/src/market/live_validators.py`` e ``live_windows.py``.
 */

/** Importo minimo valido per il prossimo rilancio su un lotto. */
export function computeMinimumNextBid(
  currentAmountCredits: number,
  hasLeader: boolean,
  minIncrementCredits: number,
): number {
  if (!hasLeader) {
    return minIncrementCredits;
  }
  return currentAmountCredits + minIncrementCredits;
}

/** Secondi residui prima della chiusura del lotto, mai negativi. */
export function secondsRemaining(closesAtIso: string, nowIso: string): number {
  const closesAt = Date.parse(closesAtIso);
  const now = Date.parse(nowIso);
  return Math.max(0, Math.round((closesAt - now) / 1000));
}

/** Se un rilancio piazzato ora ricadrebbe nella finestra di soft-close. */
export function shouldTriggerSoftClose(
  closesAtIso: string,
  nowIso: string,
  softCloseSeconds: number,
): boolean {
  return secondsRemaining(closesAtIso, nowIso) <= softCloseSeconds;
}
