/**
 * «Elimina il mio account» dal Profilo: dopo l'eliminazione il telefono dimentica anche
 * l'ultimo accesso (nome ed email di `lastUser.ts`). Prima restava e la schermata di accesso
 * mostrava «Bentornato, <nickname>» con l'email già scritta e «Accedi come…» per un account
 * che non esiste più (corsa M1, 22/11).
 *
 * Solo logica pura: i passi arrivano dal Profilo, così gira nei test `node:test`.
 */
export type AccountDeletionSteps = {
  /** `DELETE` dell'account: se fallisce non si dimentica nulla e si resta dentro. */
  deleteAccount: () => Promise<unknown>;
  /** Cancella nome ed email dell'ultimo accesso salvati sul telefono. */
  forgetLastUser: () => Promise<void>;
  /** Chiude la sessione: la schermata di accesso si apre già senza «Bentornato». */
  logout: () => Promise<void>;
};

export async function deleteAccountAndForget(steps: AccountDeletionSteps): Promise<void> {
  await steps.deleteAccount();
  await steps.forgetLastUser();
  await steps.logout();
}
