/** La pagina Inviti ricevuti è già montata: un click sulla notifica deve ricaricarla. */
const listeners = new Set<() => void>();

export function notifyReceivedInvitesChanged(): void {
  for (const listener of listeners) {
    listener();
  }
}

export function subscribeReceivedInvitesChanged(listener: () => void): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}
