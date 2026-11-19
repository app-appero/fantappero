import { useEffect, useState } from "react";
import { fetchAuthOptions } from "../api/auth";

export type AuthOptionsState = {
  /** `false` finché il server non ha risposto: nel dubbio non si mostra il modulo con email. */
  loaded: boolean;
  emailRegistrationEnabled: boolean;
  /** Con `false` (dev e pilota) dopo la registrazione si entra subito, senza email da aprire. */
  emailVerificationRequired: boolean;
};

/**
 * Opzioni di accesso del server (per il pilota la registrazione è solo con Google).
 * Se la richiesta fallisce (server irraggiungibile) si ripiega sul solo accesso con Google:
 * mostrare il modulo con email farebbe credere che sia ancora previsto, e comunque senza
 * server nessun accesso può riuscire.
 */
export function useAuthOptions(): AuthOptionsState {
  const [state, setState] = useState<AuthOptionsState>({
    loaded: false,
    emailRegistrationEnabled: false,
    emailVerificationRequired: true,
  });

  useEffect(() => {
    let cancelled = false;
    fetchAuthOptions()
      .then((options) => {
        if (!cancelled) {
          setState({
            loaded: true,
            emailRegistrationEnabled: options.emailRegistrationEnabled,
            // Server meno recenti non lo dicono: si resta sul comportamento di prima (verifica).
            emailVerificationRequired: options.emailVerificationRequired !== false,
          });
        }
      })
      .catch(() => {
        if (!cancelled) {
          setState({ loaded: true, emailRegistrationEnabled: false, emailVerificationRequired: true });
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return state;
}
