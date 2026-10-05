type Listener = () => void;

const listeners = new Set<Listener>();

/** Il badge rosso degli inviti rilegge il conteggio dopo accetta/rifiuta. */
export function notifyPendingInvitesChanged(): void {
  for (const listener of listeners) {
    listener();
  }
}

export function subscribePendingInvitesChanged(listener: Listener): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}
