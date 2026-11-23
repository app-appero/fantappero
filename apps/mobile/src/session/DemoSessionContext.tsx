import { Alert } from "react-native";
import {
  hasPermissions,
  PRIVACY_CONTACT_EMAIL,
  type AdminImpersonateResult,
  type AuthTokensResponse,
  type LeagueSummary,
  type Permission,
  type PermissionContext,
  type SessionUser,
} from "@fantappero/contracts";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import * as authApi from "../api/auth";
import { AppState } from "react-native";
import { ApiError, getApiErrorMessage, setUnauthorizedRecovery } from "../api/client";
import { fetchMyLeagues } from "../api/leagues";
import { buildPermissionContext } from "./demoSession";
import { sameLeagueList, subscribeLeagueListRefresh } from "./leagueListRefresh";
import { OFFLINE_RETRY_INTERVAL_MS, restoreSessionAtStartup } from "./startupRestore";
import {
  clearImpersonatorSession,
  clearStoredActiveLeagueId,
  clearStoredSession,
  getMemorySession,
  loadImpersonatorSession,
  loadStoredActiveLeagueId,
  loadStoredSession,
  saveImpersonatorSession,
  saveStoredActiveLeagueId,
  saveStoredSession,
  sessionPersistenceFailed,
  setMemorySession,
  type StoredSession,
} from "./sessionStorage";
import {
  isTransientApiError,
  recoverAccessToken,
  refreshSessionIfExpiring,
  refreshStoredSession,
  setSessionChangeListener,
} from "./refreshAccessToken";

export type AuthSessionContextValue = {
  user: SessionUser | null;
  isAuthenticated: boolean;
  loading: boolean;
  /** Avvio senza rete con una sessione salvata: si mostra «Connessione non disponibile». */
  sessionOffline: boolean;
  /** «Riprova» in corso su «Connessione non disponibile». */
  restoringSession: boolean;
  retrySessionRestore: () => Promise<void>;
  leagues: readonly LeagueSummary[];
  activeLeagueId: string | null;
  activeLeague: LeagueSummary | null;
  permissionContext: PermissionContext | null;
  accessToken: string | null;
  setActiveLeagueId: (leagueId: string) => void;
  updateDisplayName: (displayName: string) => void;
  can: (required: readonly Permission[]) => boolean;
  registerLeague: (league: LeagueSummary) => void;
  unregisterLeague: (leagueId: string) => void;
  patchLeague: (leagueId: string, patch: Partial<LeagueSummary>) => void;
  login: (email: string, password: string) => Promise<void>;
  loginWithGoogle: (idToken: string) => Promise<void>;
  claimGoogleHandoff: (code: string) => Promise<void>;
  logout: () => Promise<void>;
  isImpersonating: boolean;
  startImpersonation: (result: AdminImpersonateResult) => Promise<void>;
  stopImpersonation: () => Promise<void>;
  applySession: (tokens: AuthTokensResponse) => Promise<void>;
  refreshMemberships: () => Promise<LeagueSummary[]>;
};

const AuthSessionContext = createContext<AuthSessionContextValue | null>(null);

function resolvePreferredLeagueId(
  leagues: readonly LeagueSummary[],
  currentLeagueId: string | null,
): string | null {
  if (currentLeagueId && leagues.some((league) => league.id === currentLeagueId)) {
    return currentLeagueId;
  }
  return leagues[0]?.id ?? null;
}

export function AuthSessionProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<SessionUser | null>(null);
  const [loading, setLoading] = useState(true);
  const [leagues, setLeagues] = useState<LeagueSummary[]>([]);
  const [activeLeagueId, setActiveLeagueIdState] = useState<string | null>(null);
  const [accessToken, setAccessToken] = useState<string | null>(null);
  const [impersonator, setImpersonator] = useState<StoredSession | null>(null);
  /** Sessione salvata ma server irraggiungibile all'avvio (vedi `startupRestore.ts`). */
  const [sessionOffline, setSessionOffline] = useState(false);
  const [restoringSession, setRestoringSession] = useState(false);

  const clearToLoggedOut = useCallback(() => {
    setAccessToken(null);
    setMemorySession(null);
    setUser(null);
    setLeagues([]);
    setActiveLeagueIdState(null);
    setImpersonator(null);
    setSessionOffline(false);
    setLoading(false);
  }, []);

  const persistSession = useCallback(async (session: StoredSession) => {
    setMemorySession(session);
    setAccessToken(session.accessToken);
    setUser(session.user);
    await saveStoredSession(session);
    if (sessionPersistenceFailed()) {
      Alert.alert(
        "Accesso non memorizzato",
        `Il telefono non permette di ricordare l'accesso: dovrai rifare il login a ogni apertura. Se succede sempre, segnalacelo da «Segnala un problema» o scrivi a ${PRIVACY_CONTACT_EMAIL}.`,
      );
    }
  }, []);

  const mounted = useRef(true);
  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);
  const restoreInFlight = useRef<Promise<void> | null>(null);

  /**
   * Riprende la sessione salvata (all'avvio e, se il server non risponde, a ogni nuovo
   * tentativo). Le decisioni sono in `startupRestore.ts`; qui si applicano allo stato.
   */
  const restoreSession = useCallback((): Promise<void> => {
    if (restoreInFlight.current) {
      return restoreInFlight.current;
    }
    const run = (async () => {
      const outcome = await restoreSessionAtStartup({
        loadStoredSession,
        fetchMe: authApi.fetchMe,
        getMemorySession,
        isTransientError: isTransientApiError,
        loadImpersonatorSession,
        clearImpersonatorSession,
        forgetSession: async () => {
          await clearStoredSession();
          setMemorySession(null);
        },
        refreshStoredSession,
      });
      if (!mounted.current) {
        return;
      }
      if (outcome.kind === "signedOut") {
        clearToLoggedOut();
        return;
      }
      if (outcome.kind === "offline") {
        // Rete assente all'avvio: sessione tenuta, «Connessione non disponibile» (M5, 22/11).
        setSessionOffline(true);
        setLoading(false);
        return;
      }

      // Anche dopo «Connessione non disponibile»: caricamento finché non arrivano le leghe.
      setLoading(true);
      setSessionOffline(false);
      const { session } = outcome;
      if (outcome.persist) {
        await persistSession(session);
      } else {
        // Già salvata da un rinnovo appena fatto.
        setMemorySession(session);
        setAccessToken(session.accessToken);
        setUser(session.user);
      }
      if (!mounted.current) {
        return;
      }

      const paused = await loadImpersonatorSession();
      if (mounted.current) {
        setImpersonator(paused);
      }

      try {
        const memberships = await fetchMyLeagues(session.accessToken);
        if (!mounted.current) {
          return;
        }
        const storedLeagueId = await loadStoredActiveLeagueId();
        const nextLeagueId = resolvePreferredLeagueId(memberships, storedLeagueId);
        setLeagues(memberships);
        setActiveLeagueIdState(nextLeagueId);
        if (nextLeagueId) {
          await saveStoredActiveLeagueId(nextLeagueId);
        } else {
          await clearStoredActiveLeagueId();
        }
      } catch {
        // Keep memberships already in memory; a schema/API error must not
        // look like the user lost every league.
      } finally {
        if (mounted.current) {
          setLoading(false);
        }
      }
    })();
    const tracked = run.finally(() => {
      restoreInFlight.current = null;
    });
    restoreInFlight.current = tracked;
    return tracked;
  }, [clearToLoggedOut, persistSession]);

  useEffect(() => {
    void restoreSession();
  }, [restoreSession]);

  /** «Riprova» di «Connessione non disponibile». */
  const retrySessionRestore = useCallback(async () => {
    setRestoringSession(true);
    try {
      await restoreSession();
    } finally {
      if (mounted.current) {
        setRestoringSession(false);
      }
    }
  }, [restoreSession]);

  // Senza rete all'avvio l'app riprova da sola, e subito quando torna in primo piano: appena il
  // server risponde entra con la stessa sessione, senza password (M5, 22/11).
  useEffect(() => {
    if (!sessionOffline) {
      return;
    }
    const timer = setInterval(() => {
      void restoreSession();
    }, OFFLINE_RETRY_INTERVAL_MS);
    const subscription = AppState.addEventListener("change", (state) => {
      if (state === "active") {
        void restoreSession();
      }
    });
    return () => {
      clearInterval(timer);
      subscription.remove();
    };
  }, [restoreSession, sessionOffline]);

  useEffect(() => {
    setUnauthorizedRecovery((input) => recoverAccessToken(input.accessToken));
    setSessionChangeListener((session) => {
      if (!session) {
        clearToLoggedOut();
        return;
      }
      setAccessToken(session.accessToken);
      setUser(session.user);
    });
    const subscription = AppState.addEventListener("change", (state) => {
      if (state === "active") {
        void refreshSessionIfExpiring();
      }
    });
    return () => {
      setUnauthorizedRecovery(null);
      setSessionChangeListener(null);
      subscription.remove();
    };
  }, [clearToLoggedOut]);

  const applySession = useCallback(
    async (tokens: AuthTokensResponse) => {
      if (!tokens?.accessToken || !tokens?.user) {
        throw new ApiError(
          "Risposta di login incompleta dall'API.",
          0,
          "invalid_login_response",
        );
      }
      const session: StoredSession = {
        accessToken: tokens.accessToken,
        refreshToken: tokens.refreshToken,
        user: tokens.user,
      };
      await persistSession(session);
    },
    [persistSession],
  );

  const refreshMemberships = useCallback(async (): Promise<LeagueSummary[]> => {
    const token = accessToken ?? getMemorySession()?.accessToken;
    if (!token) {
      return [];
    }
    const memberships = await fetchMyLeagues(token);
    // Nessuna novità: stesso array, nessun ridisegno (si rilegge a ogni «tira per aggiornare»).
    setLeagues((current) => (sameLeagueList(current, memberships) ? current : memberships));
    setActiveLeagueIdState((current) => {
      const next = resolvePreferredLeagueId(memberships, current);
      if (next) {
        void saveStoredActiveLeagueId(next);
      } else {
        void clearStoredActiveLeagueId();
      }
      return next;
    });
    return memberships;
  }, [accessToken]);

  // Leghe create o tolte fuori dall'app (sito, API): il selettore le vede tirando una pagina
  // per aggiornarla o tornando nell'app, senza riavviarla (corsa M3, 22/11).
  const signedIn = user !== null;
  useEffect(() => {
    if (!signedIn) {
      return;
    }
    const refresh = () => {
      void refreshMemberships().catch(() => {
        // Elenco accessorio: un errore di rete lascia quello già in memoria.
      });
    };
    const unsubscribe = subscribeLeagueListRefresh(refresh);
    const subscription = AppState.addEventListener("change", (state) => {
      if (state === "active") {
        refresh();
      }
    });
    return () => {
      unsubscribe();
      subscription.remove();
    };
  }, [refreshMemberships, signedIn]);

  const login = useCallback(
    async (email: string, password: string) => {
      const tokens = await authApi.login({ email, password });
      await applySession(tokens);
      try {
        const memberships = await fetchMyLeagues(tokens.accessToken);
        const storedLeagueId = await loadStoredActiveLeagueId();
        const nextLeagueId = resolvePreferredLeagueId(memberships, storedLeagueId);
        setLeagues(memberships);
        setActiveLeagueIdState(nextLeagueId);
        if (nextLeagueId) {
          await saveStoredActiveLeagueId(nextLeagueId);
        } else {
          await clearStoredActiveLeagueId();
        }
      } catch {
        // Keep memberships already in memory.
      }
    },
    [applySession],
  );

  const loginWithGoogle = useCallback(
    async (idToken: string) => {
      const tokens = await authApi.loginWithGoogle({ idToken });
      await applySession(tokens);
      try {
        const memberships = await fetchMyLeagues(tokens.accessToken);
        const storedLeagueId = await loadStoredActiveLeagueId();
        const nextLeagueId = resolvePreferredLeagueId(memberships, storedLeagueId);
        setLeagues(memberships);
        setActiveLeagueIdState(nextLeagueId);
        if (nextLeagueId) {
          await saveStoredActiveLeagueId(nextLeagueId);
        } else {
          await clearStoredActiveLeagueId();
        }
      } catch {
        // Keep memberships already in memory.
      }
    },
    [applySession],
  );

  /**
   * One-time pickup code from the web Google handoff page — never the Google ID token or a
   * usable session token on its own (see `auth/googleAppHandoff.ts`). The code claims the
   * session the web page already created server-side.
   */
  const claimGoogleHandoff = useCallback(
    async (code: string) => {
      const tokens = await authApi.claimGoogleHandoff({ code });
      await applySession(tokens);
      try {
        const memberships = await fetchMyLeagues(tokens.accessToken);
        const storedLeagueId = await loadStoredActiveLeagueId();
        const nextLeagueId = resolvePreferredLeagueId(memberships, storedLeagueId);
        setLeagues(memberships);
        setActiveLeagueIdState(nextLeagueId);
        if (nextLeagueId) {
          await saveStoredActiveLeagueId(nextLeagueId);
        } else {
          await clearStoredActiveLeagueId();
        }
      } catch {
        // Keep memberships already in memory.
      }
    },
    [applySession],
  );

  const replaceMemberships = useCallback(async (token: string) => {
    const memberships = await fetchMyLeagues(token);
    setLeagues(memberships);
    const storedLeagueId = await loadStoredActiveLeagueId();
    const nextLeagueId = resolvePreferredLeagueId(memberships, storedLeagueId);
    setActiveLeagueIdState(nextLeagueId);
    if (nextLeagueId) {
      await saveStoredActiveLeagueId(nextLeagueId);
    } else {
      await clearStoredActiveLeagueId();
    }
  }, []);

  const startImpersonation = useCallback(
    async (result: AdminImpersonateResult) => {
      const operator = getMemorySession() ?? (await loadStoredSession());
      const alreadyPaused = await loadImpersonatorSession();
      if (!alreadyPaused && operator?.refreshToken) {
        await saveImpersonatorSession(operator);
        setImpersonator(operator);
      }
      await persistSession({
        accessToken: result.accessToken,
        refreshToken: "",
        user: result.user,
      });
      try {
        await replaceMemberships(result.accessToken);
      } catch {
        setLeagues([]);
        setActiveLeagueIdState(null);
      }
    },
    [persistSession, replaceMemberships],
  );

  const stopImpersonation = useCallback(async () => {
    const operator = (await loadImpersonatorSession()) ?? impersonator;
    if (!operator) {
      return;
    }
    await clearImpersonatorSession();
    setImpersonator(null);
    await persistSession(operator);
    try {
      await replaceMemberships(operator.accessToken);
    } catch {
      setLeagues([]);
      setActiveLeagueIdState(null);
    }
  }, [impersonator, persistSession, replaceMemberships]);

  const logout = useCallback(async () => {
    const stored = getMemorySession() ?? (await loadStoredSession());
    await clearStoredSession();
    if (stored?.refreshToken) {
      try {
        await authApi.logout({ refreshToken: stored.refreshToken });
      } catch {
        // Session already cleared locally.
      }
    }
    clearToLoggedOut();
  }, [clearToLoggedOut]);

  const setActiveLeagueId = useCallback((leagueId: string) => {
    setActiveLeagueIdState(leagueId);
    void saveStoredActiveLeagueId(leagueId);
  }, []);

  const registerLeague = useCallback((league: LeagueSummary) => {
    setLeagues((current) => {
      const existingIndex = current.findIndex((row) => row.id === league.id);
      if (existingIndex >= 0) {
        const next = [...current];
        next[existingIndex] = league;
        return next;
      }
      return [...current, league];
    });
    setActiveLeagueIdState(league.id);
    void saveStoredActiveLeagueId(league.id);
  }, []);

  const patchLeague = useCallback((leagueId: string, patch: Partial<LeagueSummary>) => {
    setLeagues((current) =>
      current.map((row) => (row.id === leagueId ? { ...row, ...patch } : row)),
    );
  }, []);

  const unregisterLeague = useCallback((leagueId: string) => {
    setLeagues((current) => {
      const next = current.filter((row) => row.id !== leagueId);
      setActiveLeagueIdState((active) => {
        if (active !== leagueId) {
          return active;
        }
        const fallback = next[0]?.id ?? null;
        if (fallback) {
          void saveStoredActiveLeagueId(fallback);
        } else {
          void clearStoredActiveLeagueId();
        }
        return fallback;
      });
      return next;
    });
  }, []);

  const updateDisplayName = useCallback((displayName: string) => {
    setUser((current) => {
      if (!current) {
        return current;
      }
      const next = { ...current, displayName };
      const stored = getMemorySession();
      if (stored) {
        const updatedSession: StoredSession = { ...stored, user: next };
        setMemorySession(updatedSession);
        void saveStoredSession(updatedSession);
      }
      return next;
    });
  }, []);

  const permissionContext = useMemo(() => {
    if (!user) {
      return null;
    }
    return buildPermissionContext(user, activeLeagueId, leagues);
  }, [user, activeLeagueId, leagues]);

  const activeLeague = permissionContext?.activeLeague ?? null;

  const can = useCallback(
    (required: readonly Permission[]) => {
      if (!permissionContext) {
        return false;
      }
      return hasPermissions(permissionContext, required);
    },
    [permissionContext],
  );

  const value = useMemo(
    (): AuthSessionContextValue => ({
      user,
      isAuthenticated: user !== null,
      loading,
      sessionOffline,
      restoringSession,
      retrySessionRestore,
      leagues,
      activeLeagueId,
      activeLeague,
      permissionContext,
      accessToken,
      setActiveLeagueId,
      updateDisplayName,
      can,
      registerLeague,
      unregisterLeague,
      patchLeague,
      login,
      loginWithGoogle,
      claimGoogleHandoff,
      logout,
      isImpersonating: impersonator !== null,
      startImpersonation,
      stopImpersonation,
      applySession,
      refreshMemberships,
    }),
    [
      user,
      loading,
      sessionOffline,
      restoringSession,
      retrySessionRestore,
      leagues,
      activeLeagueId,
      activeLeague,
      permissionContext,
      accessToken,
      setActiveLeagueId,
      updateDisplayName,
      can,
      registerLeague,
      unregisterLeague,
      patchLeague,
      login,
      loginWithGoogle,
      claimGoogleHandoff,
      logout,
      impersonator,
      startImpersonation,
      stopImpersonation,
      applySession,
      refreshMemberships,
    ],
  );

  return <AuthSessionContext.Provider value={value}>{children}</AuthSessionContext.Provider>;
}

/** Alias storico per App.tsx / import esistenti. */
export const DemoSessionProvider = AuthSessionProvider;

export function useAuthSession(): AuthSessionContextValue {
  const context = useContext(AuthSessionContext);
  if (!context) {
    throw new Error("useAuthSession must be used within AuthSessionProvider");
  }
  return context;
}

/** @deprecated Prefer useAuthSession */
export function useDemoSession(): AuthSessionContextValue {
  return useAuthSession();
}

export { getApiErrorMessage } from "../api/client";
