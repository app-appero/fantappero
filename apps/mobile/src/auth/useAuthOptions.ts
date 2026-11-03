import { useEffect, useState } from "react";
import { fetchAuthOptions } from "../api/auth";

export type AuthOptionsState = {
  /** `false` finché il server non ha risposto: nel dubbio non si mostra il modulo con email. */
  loaded: boolean;
  emailRegistrationEnabled: boolean;
};

/**
 * Opzioni di accesso del server (per il pilota la registrazione è solo con Google).
 * Se la richiesta fallisce si ripiega sul modulo con email: è il server a rifiutare,
 * con un messaggio chiaro, e nessuno resta bloccato per un errore di rete.
 */
export function useAuthOptions(): AuthOptionsState {
  const [state, setState] = useState<AuthOptionsState>({ loaded: false, emailRegistrationEnabled: false });

  useEffect(() => {
    let cancelled = false;
    fetchAuthOptions()
      .then((options) => {
        if (!cancelled) {
          setState({ loaded: true, emailRegistrationEnabled: options.emailRegistrationEnabled });
        }
      })
      .catch(() => {
        if (!cancelled) {
          setState({ loaded: true, emailRegistrationEnabled: true });
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return state;
}
