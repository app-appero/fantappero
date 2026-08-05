import { hasPermissions, type Permission, type PermissionContext } from "@fantappero/contracts";
import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import {
  buildPermissionContext,
  type DemoPersona,
  resolveDemoLeagues,
  resolveDemoUser,
  resolveInitialLeagueId,
} from "./demoSession";

export type DemoSessionContextValue = {
  persona: DemoPersona;
  setPersona: (persona: DemoPersona) => void;
  logout: () => void;
  directoryAvailable: boolean;
  setDirectoryAvailable: (available: boolean) => void;
  user: ReturnType<typeof resolveDemoUser>;
  leagues: ReturnType<typeof resolveDemoLeagues>;
  activeLeagueId: string | null;
  setActiveLeagueId: (leagueId: string) => void;
  permissionContext: PermissionContext;
  can: (required: readonly Permission[]) => boolean;
};

const DemoSessionContext = createContext<DemoSessionContextValue | null>(null);

export function DemoSessionProvider({ children }: { children: ReactNode }) {
  const [persona, setPersona] = useState<DemoPersona>("member");
  const [directoryAvailable, setDirectoryAvailable] = useState(false);
  const user = useMemo(() => resolveDemoUser(persona), [persona]);
  const leagues = useMemo(() => resolveDemoLeagues(persona), [persona]);
  const [activeLeagueId, setActiveLeagueId] = useState<string | null>(() =>
    resolveInitialLeagueId("member", resolveDemoLeagues("member")),
  );

  const handlePersonaChange = useCallback(
    (next: DemoPersona) => {
      const nextLeagues = resolveDemoLeagues(next);
      setPersona(next);
      setActiveLeagueId(resolveInitialLeagueId(next, nextLeagues));
    },
    [],
  );

  const logout = useCallback(() => {
    const nextLeagues = resolveDemoLeagues("member");
    setPersona("member");
    setActiveLeagueId(resolveInitialLeagueId("member", nextLeagues));
  }, []);

  const permissionContext = useMemo(
    () => buildPermissionContext(user, activeLeagueId, leagues),
    [user, activeLeagueId, leagues],
  );

  const can = useCallback(
    (required: readonly Permission[]) => hasPermissions(permissionContext, required),
    [permissionContext],
  );

  const value = useMemo(
    (): DemoSessionContextValue => ({
      persona,
      setPersona: handlePersonaChange,
      logout,
      directoryAvailable,
      setDirectoryAvailable,
      user,
      leagues,
      activeLeagueId,
      setActiveLeagueId,
      permissionContext,
      can,
    }),
    [
      persona,
      handlePersonaChange,
      logout,
      directoryAvailable,
      user,
      leagues,
      activeLeagueId,
      permissionContext,
      can,
    ],
  );

  return <DemoSessionContext.Provider value={value}>{children}</DemoSessionContext.Provider>;
}

export function useDemoSession(): DemoSessionContextValue {
  const context = useContext(DemoSessionContext);
  if (!context) {
    throw new Error("useDemoSession must be used within DemoSessionProvider");
  }
  return context;
}
