import type { CreditLedgerList } from "@fantappero/contracts";

/**
 * Movimenti dal più recente (come sul web). Il server li manda dal più vecchio, già
 * nell'ordine in cui il saldo si è mosso: a parità di orario (stesso millisecondo) si tiene
 * quell'ordine, rovesciato. Prima a parità si ordinava per id, che è casuale.
 */
export function sortLedgerNewestFirst(entries: CreditLedgerList["entries"]) {
  return entries
    .map((entry, index) => ({ entry, index, time: Date.parse(entry.createdAt) }))
    .sort((left, right) => right.time - left.time || right.index - left.index)
    .map(({ entry }) => entry);
}
