import {
  hasPermissions,
  type LeagueSummary,
  type Permission,
  type PermissionContext,
  type SessionUser,
} from "@fantappero/contracts";
import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { useSearchParams } from "../router/simpleRouter";
import {
  buildPermissionContext,
  resolveDemoLeagues,
  resolveDemoUser,
  resolveInitialLeagueId,
} from "./demoSession";

export type AuthContextValue = {
  user: SessionUser;
  leagues: readonly LeagueSummary[];
  activeLeagueId: string | null;
  activeLeague: LeagueSummary | null;
  permissionContext: PermissionContext;
  setActiveLeagueId: (leagueId: string) => void;
  can: (required: readonly Permission[]) => boolean;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export type AuthProviderProps = {
  children: ReactNode;
};

export function AuthProvider({ children }: AuthProviderProps) {
  const [searchParams] = useSearchParams();
  const user = useMemo(() => resolveDemoUser(searchParams.toString()), [searchParams]);
  const leagues = useMemo(() => resolveDemoLeagues(searchParams.toString()), [searchParams]);
  const [activeLeagueId, setActiveLeagueIdState] = useState<string | null>(() =>
    resolveInitialLeagueId(searchParams.toString(), resolveDemoLeagues(searchParams.toString())),
  );

  const setActiveLeagueId = useCallback((leagueId: string) => {
    setActiveLeagueIdState(leagueId);
  }, []);

  const permissionContext = useMemo(
    () => buildPermissionContext(user, activeLeagueId, leagues),
    [user, activeLeagueId, leagues],
  );

  const activeLeague = permissionContext.activeLeague;

  const can = useCallback(
    (required: readonly Permission[]) => hasPermissions(permissionContext, required),
    [permissionContext],
  );

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      leagues,
      activeLeagueId,
      activeLeague,
      permissionContext,
      setActiveLeagueId,
      can,
    }),
    [user, leagues, activeLeagueId, activeLeague, permissionContext, setActiveLeagueId, can],
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
