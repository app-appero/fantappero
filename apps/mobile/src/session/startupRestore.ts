/**
 * Ripresa della sessione salvata all'avvio dell'app.
 *
 * Con la rete assente (modalità aereo) `fetchMe` falliva con un errore di rete: la sessione
 * restava salvata ma l'utente non veniva mai impostato, e l'app mostrava la schermata di
 * accesso («Bentornato») senza nessun messaggio; tornata la rete restava lì finché non la si
 * chiudeva e riapriva (corsa M5, 22/11). Ora quel caso è `offline`: l'app mostra
 * «Connessione non disponibile» con «Riprova», riprova da sola e, appena la rete torna, entra
 * con la stessa sessione senza chiedere la password.
 *
 * Solo logica pura e import di tipo: archivio e API arrivano dal chiamante, così gira nei test
 * `node:test`.
 */
import type { SessionUser } from "@fantappero/contracts";
import type { StoredSession } from "./sessionStorage";

export type StartupRestoreDeps = {
  loadStoredSession: () => Promise<StoredSession | null>;
  fetchMe: (accessToken: string) => Promise<SessionUser>;
  /** Sessione in memoria: diversa da quella salvata se una richiesta l'ha appena rinnovata. */
  getMemorySession: () => StoredSession | null;
  /** Rete assente, server irraggiungibile o 5xx (`isTransientApiError`). */
  isTransientError: (error: unknown) => boolean;
  loadImpersonatorSession: () => Promise<StoredSession | null>;
  clearImpersonatorSession: () => Promise<void>;
  /** Cancella la sessione salvata e quella in memoria. */
  forgetSession: () => Promise<void>;
  /** Rinnovo con il refresh token, sulla stessa corsia degli altri rinnovi. */
  refreshStoredSession: () => Promise<string | null>;
};

export type StartupRestore =
  /** Nessuna sessione valida: schermata di accesso. */
  | { kind: "signedOut" }
  /** Sessione salvata ma server irraggiungibile: «Connessione non disponibile», sessione tenuta. */
  | { kind: "offline" }
  /** Sessione ripresa; `persist` = da salvare (falso se un rinnovo l'ha già salvata). */
  | { kind: "signedIn"; session: StoredSession; persist: boolean };

export async function restoreSessionAtStartup(deps: StartupRestoreDeps): Promise<StartupRestore> {
  const stored = await deps.loadStoredSession();
  if (!stored) {
    return { kind: "signedOut" };
  }
  try {
    const me = await deps.fetchMe(stored.accessToken);
    return { kind: "signedIn", session: { ...stored, user: me }, persist: true };
  } catch (error) {
    const renewed = deps.getMemorySession();
    if (renewed && renewed.accessToken !== stored.accessToken) {
      return { kind: "signedIn", session: renewed, persist: false };
    }
    if (deps.isTransientError(error)) {
      // Rete assente all'avvio: non è un login fallito, la sessione resta salvata.
      return { kind: "offline" };
    }
    if (!stored.refreshToken) {
      // Impersonificazione senza refresh token: si torna alla sessione dell'operatore.
      const operator = await deps.loadImpersonatorSession();
      if (!operator) {
        await deps.forgetSession();
        return { kind: "signedOut" };
      }
      await deps.clearImpersonatorSession();
      return { kind: "signedIn", session: operator, persist: true };
    }
    try {
      // Stessa corsia degli altri rinnovi: il refresh token è monouso, due rinnovi in
      // parallelo ne brucerebbero uno e butterebbero fuori l'utente.
      const renewedToken = await deps.refreshStoredSession();
      const renewedSession = deps.getMemorySession();
      if (!renewedToken || !renewedSession) {
        return { kind: "signedOut" };
      }
      return { kind: "signedIn", session: renewedSession, persist: true };
    } catch (refreshError) {
      if (deps.isTransientError(refreshError)) {
        return { kind: "offline" };
      }
      await deps.forgetSession();
      return { kind: "signedOut" };
    }
  }
}

/** Ogni quanto l'app riprova da sola mentre mostra «Connessione non disponibile». */
export const OFFLINE_RETRY_INTERVAL_MS = 5_000;

export type StartupGate = "loading" | "offline" | "auth" | "app";

/** Cosa mostra la radice della navigazione. */
export function startupGate(input: {
  loading: boolean;
  isAuthenticated: boolean;
  sessionOffline: boolean;
}): StartupGate {
  if (input.loading) {
    return "loading";
  }
  if (input.isAuthenticated) {
    return "app";
  }
  return input.sessionOffline ? "offline" : "auth";
}
