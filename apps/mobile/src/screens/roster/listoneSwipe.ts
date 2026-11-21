/**
 * Cosa fa lo scorrimento di una riga del listone («Inserimento manuale»): a destra assegna, a
 * sinistra rimuove. Con il ruolo al completo (segnalazione di un tester, Rosario 21/11) lo
 * scorrimento a destra non assegna più e la riga dice il motivo, invece di non fare nulla.
 *
 * Solo logica pura: il motivo arriva già scritto da `roleQuotaBlockReason` di
 * `@fantappero/contracts`, uguale sul sito.
 */
export type ListoneSwipeInput = {
  /** Il calciatore è già in una rosa della lega. */
  owned: boolean;
  /** Chi guarda può rimuoverlo dalla rosa che lo ha. */
  canRelease: boolean;
  busy: boolean;
  emptySlotsCount: number;
  /** Prezzo d'acquisto valido (almeno 1). */
  priceValid: boolean;
  /** Motivo del ruolo al completo, `null` se il ruolo ha posto. */
  quotaReason: string | null;
};

export type ListoneSwipeDecision = {
  /** Lo scorrimento a destra assegna. */
  assign: boolean;
  /** Lo scorrimento a sinistra rimuove. */
  release: boolean;
  /** Scorrimento a destra tentato ma bloccato: il motivo da mostrare sulla riga. */
  blockedReason: string | null;
};

export function listoneSwipeDecision(input: ListoneSwipeInput): ListoneSwipeDecision {
  if (input.owned) {
    // Rimuovere resta possibile anche con il ruolo pieno: è il modo per fare posto.
    return { assign: false, release: input.canRelease && !input.busy, blockedReason: null };
  }
  if (input.busy || input.emptySlotsCount <= 0) {
    // Rosa piena: come prima, nessun gesto e nessun nuovo messaggio.
    return { assign: false, release: false, blockedReason: null };
  }
  if (input.quotaReason) {
    return { assign: false, release: false, blockedReason: input.quotaReason };
  }
  return { assign: input.priceValid, release: false, blockedReason: null };
}

/** Etichetta della scheda del ruolo con il conto, «Attaccanti 10/10»; «Tutti» resta com'è. */
export function roleTabLabel(label: string, stat: { filled: number; max: number } | null | undefined): string {
  return stat ? `${label} ${stat.filled}/${stat.max}` : label;
}
