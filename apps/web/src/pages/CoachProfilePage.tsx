import { Breadcrumb, PageContainer, UiStatePanel } from "@fantappero/ui";
import { useEffect, useState } from "react";
import type { FantasyCoachProfile } from "@fantappero/contracts";
import { CoachProfilePanel, DEMO_MANAGERS, DEMO_PLACEMENTS } from "../components/ManagerDirectory";
import { fetchCoachProfile } from "../api/managerInvites";
import { getApiErrorMessage, useAuth } from "../auth/AuthContext";
import { loadStoredSession } from "../auth/sessionStorage";
import { useLocation, useNavigate } from "../router/simpleRouter";

function demoProfileFor(userId: string): FantasyCoachProfile | null {
  const manager = DEMO_MANAGERS.find((item) => item.userId === userId);
  if (!manager) return null;
  const placements = DEMO_PLACEMENTS[manager.userId] ?? [];
  return {
    userId: manager.userId,
    displayName: manager.displayName,
    avatarUrl: manager.avatarUrl,
    userType: manager.userType,
    availableForInvites: manager.availableForInvites,
    namedInviteStatus: manager.namedInviteStatus,
    memberSince: manager.memberSince,
    concludedLeagues: manager.concludedLeagues,
    bestPosition: manager.bestPosition,
    historySummary: manager.historySummary,
    placements,
    placementsPage: 1,
    placementsPageSize: 20,
    placementsTotal: placements.length,
  };
}

export function CoachProfilePage({ userId }: { userId: string }) {
  const { activeLeagueId, isDemoMode } = useAuth();
  const { search } = useLocation();
  const navigate = useNavigate();
  const leagueId = new URLSearchParams(search).get("league") || activeLeagueId;

  const [profile, setProfile] = useState<FantasyCoachProfile | null>(() =>
    isDemoMode ? demoProfileFor(userId) : null,
  );
  const [loading, setLoading] = useState(!isDemoMode);
  const [error, setError] = useState<string | null>(() =>
    isDemoMode && !demoProfileFor(userId) ? "Fantallenatore non trovato (demo)." : null,
  );

  useEffect(() => {
    if (isDemoMode) {
      return;
    }
    if (!leagueId) {
      setError("Seleziona una lega amministrata per consultare il profilo.");
      setLoading(false);
      return;
    }
    const session = loadStoredSession();
    if (!session?.accessToken) {
      setError("Sessione non disponibile. Accedi di nuovo.");
      setLoading(false);
      return;
    }
    let cancelled = false;
    setLoading(true);
    setError(null);
    fetchCoachProfile(session.accessToken, leagueId, userId)
      .then((result) => {
        if (!cancelled) setProfile(result);
      })
      .catch((fetchError) => {
        if (!cancelled) setError(getApiErrorMessage(fetchError, "Impossibile caricare il profilo."));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [isDemoMode, leagueId, userId]);

  return (
    <PageContainer
      title={profile?.displayName ?? "Profilo fantallenatore"}
      header={
        <Breadcrumb
          items={[
            { label: "Fantallenatori", href: "/fantallenatori" },
            { label: profile?.displayName ?? "Profilo" },
          ]}
        />
      }
    >
      {loading ? (
        <UiStatePanel
          state="loading"
          title="Caricamento profilo"
          message="Recupero dei dati in corso…"
          testId="coach-profile-page-loading"
        />
      ) : null}
      {!loading && error ? (
        <UiStatePanel
          state="error"
          title="Profilo non disponibile"
          message={error}
          testId="coach-profile-page-error"
        />
      ) : null}
      {!loading && !error && profile ? (
        <CoachProfilePanel
          profile={profile}
          closeLabel="Torna alla directory"
          onClose={() => navigate("/fantallenatori")}
        />
      ) : null}
    </PageContainer>
  );
}
