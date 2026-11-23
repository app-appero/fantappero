/**
 * Turno che la Formazione apre a ogni caricamento (apertura, tira per aggiornare).
 *
 * Se l'amministratore o l'operatore ha scelto un turno da «Strumenti › Cambia turno», resta
 * quello finché esiste nell'elenco: tirando la pagina per aggiornarla l'app tornava al turno in
 * corso e perdeva la scelta (corsa M3, 22/11). Senza una scelta, o se il turno scelto non c'è
 * più (es. altra lega), vale il turno di default di Turni (`resolveDefaultEuropeanTurn`).
 *
 * Solo logica pura: il turno di default arriva dal chiamante, così gira nei test `node:test`.
 */
export function formationRoundToLoad<T extends { id: string }>(
  turns: readonly T[],
  pickedRoundId: string | null | undefined,
  defaultTurn: T | null,
): T | null {
  if (pickedRoundId) {
    const picked = turns.find((turn) => turn.id === pickedRoundId);
    if (picked) {
      return picked;
    }
  }
  return defaultTurn;
}
