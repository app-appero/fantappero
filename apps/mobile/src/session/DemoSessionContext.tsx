import {
  hasPermissions,
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
  useState,
  type ReactNode,
} from "react";
import * as authApi from "../api/auth";
import { ApiError } from "../api/client";
import { fetchMyLeagues } from "../api/leagues";
import { buildPermissionContext } from "./demoSession";
import {
  clearStoredActiveLeagueId,
  clearStoredSession,
  getMemorySession,
  loadStoredActiveLeagueId,
  loadStoredSession,
  saveStoredActiveLeagueId,
  saveStoredSession,
  setMemorySession,
  type StoredSession,
} from "./sessionStorage";

export type AuthSessionContextValue = {
  user: SessionUser | null;
  isAuthenticated: boolean;
  loading: boolean;
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
  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
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

  const clearToLoggedOut = useCallback(() => {
    setAccessToken(null);
    setMemorySession(null);
    setUser(null);
    setLeagues([]);
    setActiveLeagueIdState(null);
    setLoading(false);
  }, []);

  const persistSession = useCallback(async (session: StoredSession) => {
    setMemorySession(session);
    setAccessToken(session.accessToken);
    setUser(session.user);
    await saveStoredSession(session);
  }, []);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      const stored = await loadStoredSession();
      if (!stored) {
        if (!cancelled) {
          clearToLoggedOut();
        }
        return;
      }

      let session = stored;
      try {
        const me = await authApi.fetchMe(session.accessToken);
        session = { ...session, user: me };
        await persistSession(session);
      } catch {
        try {
          const refreshed = await authApi.refresh({ refreshToken: session.refreshToken });
          session = {
            accessToken: refreshed.accessToken,
            refreshToken: refreshed.refreshToken,
            user: refreshed.user,
          };
          await persistSession(session);
        } catch {
          await clearStoredSession();
          setMemorySession(null);
          if (!cancelled) {
            clearToLoggedOut();
          }
          return;
        }
      }

      if (cancelled) {
        return;
      }

      try {
        const memberships = await fetchMyLeagues(session.accessToken);
        if (cancelled) {
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
        if (!cancelled) {
          setLeagues([]);
          setActiveLeagueIdState(null);
          await clearStoredActiveLeagueId();
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [clearToLoggedOut, persistSession]);

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
    setLeagues(memberships);
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
        setLeagues([]);
        setActiveLeagueIdState(null);
        await clearStoredActiveLeagueId();
      }
    },
    [applySession],
  );

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
      login,
      logout,
      applySession,
      refreshMemberships,
    }),
    [
      user,
      loading,
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
      login,
      logout,
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

export function getApiErrorMessage(error: unknown, fallback: string): string {
  if (error instanceof ApiError) {
    return error.message;
  }
  return fallback;
}
