import { hasPermissions, type Permission } from "@fantappero/contracts";
import { UiStatePanel } from "@fantappero/ui";
import { type ReactNode, useEffect, useMemo } from "react";
import { useAuth } from "../auth/AuthContext";
import { useLocation } from "../router/simpleRouter";

export type RequirePermissionsProps = {
  required: readonly Permission[];
  children: ReactNode;
};

/** Client-side gate — server remains authoritative (EP02-03). */
export function RequirePermissions({ required, children }: RequirePermissionsProps) {
  const { can, user, loading, leagues, activeLeagueId, setActiveLeagueId } = useAuth();
  const { search } = useLocation();

  const requestedLeagueId = useMemo(
    () => new URLSearchParams(search).get("leagueId"),
    [search],
  );

  const requestedLeague = useMemo(() => {
    if (!requestedLeagueId) {
      return null;
    }
    return leagues.find((league) => league.id === requestedLeagueId) ?? null;
  }, [leagues, requestedLeagueId]);

  const requestedLeagueAllowed = useMemo(() => {
    if (!user || !requestedLeague) {
      return false;
    }
    return hasPermissions({ user, activeLeague: requestedLeague }, required);
  }, [required, requestedLeague, user]);

  const activeLeagueAllowed = can(required);
  const isAllowed = requestedLeagueId ? requestedLeagueAllowed : activeLeagueAllowed;

  const fallbackLeagueId = useMemo(() => {
    if (!user || requestedLeagueId) {
      return null;
    }
    return (
      leagues.find((league) => hasPermissions({ user, activeLeague: league }, required))?.id ?? null
    );
  }, [leagues, requestedLeagueId, required, user]);

  useEffect(() => {
    if (!user || loading) {
      return;
    }

    if (requestedLeagueId && requestedLeagueAllowed && requestedLeagueId !== activeLeagueId) {
      setActiveLeagueId(requestedLeagueId);
      return;
    }

    if (!requestedLeagueId && !isAllowed && fallbackLeagueId && fallbackLeagueId !== activeLeagueId) {
      setActiveLeagueId(fallbackLeagueId);
    }
  }, [
    activeLeagueId,
    fallbackLeagueId,
    isAllowed,
    loading,
    requestedLeagueAllowed,
    requestedLeagueId,
    setActiveLeagueId,
    user,
  ]);

  if (!user) {
    return (
      <UiStatePanel
        state="empty"
        title="Accesso richiesto"
        message="Accedi per visualizzare questa sezione."
        testId="route-unauthenticated"
      />
    );
  }

  if (loading) {
    return (
      <UiStatePanel
        state="loading"
        title="Verifica permessi"
        message="Controllo autorizzazioni in corso…"
        testId="route-loading"
      />
    );
  }

  if (!isAllowed) {
    if (!requestedLeagueId && fallbackLeagueId && fallbackLeagueId !== activeLeagueId) {
      return (
        <UiStatePanel
          state="loading"
          title="Selezione lega"
          message="Seleziono una lega in cui hai i permessi richiesti…"
          testId="route-switching-league"
        />
      );
    }

    return (
      <UiStatePanel
        state="forbidden"
        title="Permessi insufficienti"
        message="Non hai accesso a questa sezione. Contatta l'amministratore di lega se pensi sia un errore."
        testId="route-forbidden"
      />
    );
  }

  return <>{children}</>;
}

export type RequireGlobalOperatorProps = {
  children: ReactNode;
};

export function RequireGlobalOperator({ children }: RequireGlobalOperatorProps) {
  const { user } = useAuth();

  if (!user || user.globalRole !== "global_operator") {
    return (
      <UiStatePanel
        state="forbidden"
        title="Area riservata"
        message="Il pannello operatore globale è accessibile solo allo staff piattaforma."
        testId="route-forbidden"
      />
    );
  }

  return <>{children}</>;
}
