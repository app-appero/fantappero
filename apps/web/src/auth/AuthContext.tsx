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
import { useSearchParams } from "../router/simpleRouter";
import {
  buildPermissionContext,
  resolveDemoLeagues,
  resolveDemoUser,
  resolveInitialLeagueId,
} from "./demoSession";
import {
  clearStoredActiveLeagueId,
  clearStoredSession,
  loadStoredActiveLeagueId,
  loadStoredMyLeagues,
  loadStoredSession,
  saveStoredActiveLeagueId,
  saveStoredMyLeagues,
  saveStoredSession,
} from "./sessionStorage";

export type AuthContextValue = {
  user: SessionUser | null;
  isAuthenticated: boolean;
  isDemoMode: boolean;
  loading: boolean;
  leagues: readonly LeagueSummary[];
  activeLeagueId: string | null;
  activeLeague: LeagueSummary | null;
  permissionContext: PermissionContext | null;
  setActiveLeagueId: (leagueId: string) => void;
  can: (required: readonly Permission[]) => boolean;
  registerLeague: (league: LeagueSummary) => void;
  unregisterLeague: (leagueId: string) => void;
  patchLeague: (leagueId: string, patch: Partial<LeagueSummary>) => void;
  leaguesError: string | null;
  refreshLeagues: () => Promise<void>;
  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  applySession: (tokens: AuthTokensResponse) => void;
  updateDisplayName: (displayName: string) => void;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export type AuthProviderProps = {
  children: ReactNode;
};

function isDemoPersonaActive(search: string | URLSearchParams): boolean {
  if (!import.meta.env.DEV) {
    return false;
  }
  const params = search instanceof URLSearchParams ? search : new URLSearchParams(search);
  return params.has("persona");
}

function resolvePreferredLeagueId(
  leagues: readonly LeagueSummary[],
  currentLeagueId: string | null,
): string | null {
  if (currentLeagueId && leagues.some((league) => league.id === currentLeagueId)) {
    return currentLeagueId;
  }
  return leagues[0]?.id ?? null;
}

export function AuthProvider({ children }: AuthProviderProps) {
  const [searchParams] = useSearchParams();
  const isDemoMode = isDemoPersonaActive(searchParams);
  const demoUser = useMemo(() => resolveDemoUser(searchParams), [searchParams, isDemoMode]);
  const demoLeagues = useMemo(() => resolveDemoLeagues(searchParams), [searchParams, isDemoMode]);

  const [user, setUser] = useState<SessionUser | null>(() => {
    if (isDemoMode) {
      return demoUser;
    }
    return loadStoredSession()?.user ?? null;
  });
  const [loading, setLoading] = useState(() => {
    if (isDemoMode) {
      return false;
    }
    return loadStoredSession() !== null;
  });
  const [leaguesState, setLeaguesState] = useState<LeagueSummary[]>(() =>
    isDemoMode ? [] : loadStoredMyLeagues(loadStoredSession()?.user.id ?? null),
  );
  const [leaguesError, setLeaguesError] = useState<string | null>(null);
  const [demoLeaguePatches, setDemoLeaguePatches] = useState<Record<string, Partial<LeagueSummary>>>(
    {},
  );
  const [activeLeagueId, setActiveLeagueIdState] = useState<string | null>(() =>
    isDemoMode ? resolveInitialLeagueId(searchParams, demoLeagues) : loadStoredActiveLeagueId(),
  );
  const leagues = useMemo(() => {
    const base = isDemoMode ? demoLeagues : leaguesState;
    if (!isDemoMode) {
      return base;
    }
    return base.map((row) => {
      const patch = demoLeaguePatches[row.id];
      return patch ? { ...row, ...patch } : row;
    });
  }, [demoLeaguePatches, demoLeagues, isDemoMode, leaguesState]);

  const applyMemberships = useCallback((memberships: LeagueSummary[], userId: string) => {
    setLeaguesError(null);
    setLeaguesState(memberships);
    saveStoredMyLeagues(userId, memberships);
    setActiveLeagueIdState((current) => {
      const nextLeagueId = resolvePreferredLeagueId(
        memberships,
        current ?? loadStoredActiveLeagueId(),
      );
      if (nextLeagueId) {
        saveStoredActiveLeagueId(nextLeagueId);
      } else {
        clearStoredActiveLeagueId();
      }
      return nextLeagueId;
    });
  }, []);

  useEffect(() => {
    if (isDemoMode || !user) {
      return;
    }
    saveStoredMyLeagues(user.id, leaguesState);
  }, [isDemoMode, leaguesState, user]);

  useEffect(() => {
    if (isDemoMode) {
      setUser(demoUser);
      setActiveLeagueIdState(resolveInitialLeagueId(searchParams, demoLeagues));
      setLeaguesError(null);
      setLoading(false);
      return;
    }

    const stored = loadStoredSession();
    if (!stored) {
      setUser(null);
      setLeaguesState([]);
      setLeaguesError(null);
      setActiveLeagueIdState(null);
      clearStoredActiveLeagueId();
      setLoading(false);
      return;
    }

    let cancelled = false;
    void (async () => {
      let accessToken = stored.accessToken;
      let sessionUser: SessionUser;
      try {
        sessionUser = await authApi.fetchMe(accessToken);
      } catch {
        try {
          const refreshed = await authApi.refresh({ refreshToken: stored.refreshToken });
          saveStoredSession({
            accessToken: refreshed.accessToken,
            refreshToken: refreshed.refreshToken,
            user: refreshed.user,
          });
          accessToken = refreshed.accessToken;
          sessionUser = refreshed.user;
        } catch {
          if (cancelled) {
            return;
          }
          clearStoredSession();
          clearStoredActiveLeagueId();
          setUser(null);
          setLeaguesState([]);
          setActiveLeagueIdState(null);
          setLoading(false);
          return;
        }
      }

      if (cancelled) {
        return;
      }
      setUser(sessionUser);

      try {
        const memberships = await fetchMyLeagues(accessToken);
        if (cancelled) {
          return;
        }
        setLeaguesError(null);
        applyMemberships(memberships, sessionUser.id);
      } catch (cause) {
        if (cancelled) {
          return;
        }
        setLeaguesError(getApiErrorMessage(cause, "Impossibile caricare le tue leghe."));
        setActiveLeagueIdState((current) => {
          if (current) {
            return current;
          }
          const cached = loadStoredMyLeagues(sessionUser.id);
          return resolvePreferredLeagueId(cached, loadStoredActiveLeagueId());
        });
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [isDemoMode, demoLeagues, demoUser, searchParams, applyMemberships]);

  const applySession = useCallback((tokens: AuthTokensResponse) => {
    saveStoredSession({
      accessToken: tokens.accessToken,
      refreshToken: tokens.refreshToken,
      user: tokens.user,
    });
    setUser(tokens.user);
  }, []);

  const updateDisplayName = useCallback((displayName: string) => {
    setUser((current) => {
      if (!current) {
        return current;
      }
      const nextUser = { ...current, displayName };
      const stored = loadStoredSession();
      if (stored) {
        saveStoredSession({ ...stored, user: nextUser });
      }
      return nextUser;
    });
  }, []);

  const login = useCallback(
    async (email: string, password: string) => {
      const tokens = await authApi.login({ email, password });
      applySession(tokens);

      if (isDemoMode) {
        return;
      }
      setLeaguesState(loadStoredMyLeagues(tokens.user.id));
      try {
        const memberships = await fetchMyLeagues(tokens.accessToken);
        applyMemberships(memberships, tokens.user.id);
      } catch (cause) {
        setLeaguesError(getApiErrorMessage(cause, "Impossibile caricare le tue leghe."));
      }
    },
    [applyMemberships, applySession, isDemoMode],
  );

  const refreshLeagues = useCallback(async () => {
    if (isDemoMode) {
      return;
    }
    const stored = loadStoredSession();
    if (!stored) {
      return;
    }
    try {
      const memberships = await fetchMyLeagues(stored.accessToken);
      applyMemberships(memberships, stored.user.id);
    } catch (cause) {
      setLeaguesError(getApiErrorMessage(cause, "Impossibile caricare le tue leghe."));
    }
  }, [applyMemberships, isDemoMode]);

  const logout = useCallback(async () => {
    const stored = loadStoredSession();
    clearStoredSession();
    clearStoredActiveLeagueId();
    setUser(null);
    setLeaguesState([]);
    setLeaguesError(null);
    setActiveLeagueIdState(null);
    if (stored?.refreshToken) {
      try {
        await authApi.logout({ refreshToken: stored.refreshToken });
      } catch {
        // Session already cleared locally.
      }
    }
  }, []);

  const setActiveLeagueId = useCallback((leagueId: string) => {
    setActiveLeagueIdState(leagueId);
    if (!isDemoMode) {
      saveStoredActiveLeagueId(leagueId);
    }
  }, [isDemoMode]);

  const registerLeague = useCallback(
    (league: LeagueSummary) => {
      if (isDemoMode) {
        return;
      }
      setLeaguesState((current) => {
        const existingIndex = current.findIndex((row) => row.id === league.id);
        if (existingIndex >= 0) {
          const next = [...current];
          next[existingIndex] = league;
          return next;
        }
        return [...current, league];
      });
      setActiveLeagueIdState(league.id);
      saveStoredActiveLeagueId(league.id);
    },
    [isDemoMode],
  );

  const patchLeague = useCallback(
    (leagueId: string, patch: Partial<LeagueSummary>) => {
      if (isDemoMode) {
        setDemoLeaguePatches((current) => ({
          ...current,
          [leagueId]: { ...current[leagueId], ...patch },
        }));
        return;
      }
      setLeaguesState((current) =>
        current.map((row) => (row.id === leagueId ? { ...row, ...patch } : row)),
      );
    },
    [isDemoMode],
  );

  const unregisterLeague = useCallback(
    (leagueId: string) => {
      if (isDemoMode) {
        return;
      }
      setLeaguesState((current) => {
        const next = current.filter((row) => row.id !== leagueId);
        setActiveLeagueIdState((active) => {
          if (active !== leagueId) {
            return active;
          }
          const fallback = next[0]?.id ?? null;
          if (fallback) {
            saveStoredActiveLeagueId(fallback);
          } else {
            clearStoredActiveLeagueId();
          }
          return fallback;
        });
        return next;
      });
    },
    [isDemoMode],
  );

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

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      isAuthenticated: user !== null,
      isDemoMode,
      loading,
      leagues,
      leaguesError,
      activeLeagueId,
      activeLeague,
      permissionContext,
      setActiveLeagueId,
      can,
      registerLeague,
      unregisterLeague,
      patchLeague,
      login,
      refreshLeagues,
      logout,
      applySession,
      updateDisplayName,
    }),
    [
      user,
      isDemoMode,
      loading,
      leagues,
      leaguesError,
      activeLeagueId,
      activeLeague,
      permissionContext,
      setActiveLeagueId,
      can,
      registerLeague,
      unregisterLeague,
      patchLeague,
      login,
      refreshLeagues,
      logout,
      applySession,
      updateDisplayName,
    ],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within AuthProvider");
  }
  return context;
}

export function getApiErrorMessage(error: unknown, fallback: string): string {
  if (error instanceof ApiError) {
    return error.message;
  }
  if (error instanceof Error && error.message.trim()) {
    return error.message;
  }
  return fallback;
}
