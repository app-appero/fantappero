import type { H2HMatchupDetail, H2HPlayerScore, H2HSideLineup } from "@fantappero/contracts";
import {
  Badge,
  Breadcrumb,
  Button,
  FormationView,
  PageContainer,
  UiStatePanel,
  type FormationSlot,
} from "@fantappero/ui";
import { useCallback, useEffect, useState } from "react";
import { fetchH2HMatchup } from "../api/leagues";
import { getApiErrorMessage, useAuth } from "../auth/AuthContext";
import { loadStoredSession } from "../auth/sessionStorage";
import { useLiveMatchupPolling } from "../matchday/useLiveMatchupPolling";
import { Link, useLocation } from "../router/simpleRouter";
import { parseWireframeStateFromSearch } from "../wireframes/useWireframeState";

const DEMO_DETAIL: H2HMatchupDetail = {
  slotId: "slot-demo-1",
  leagueId: "lega-demo",
  roundNumber: 1,
  fantasyRoundId: "turn-demo-1",
  homologationStatus: "provisional",
  europeanTurnStatus: "locked",
  live: true,
  isBye: false,
  home: {
    fantasyTeamId: "team-a",
    teamName: "Marco FC",
    displayName: "Marco",
    module: "4-3-3",
    lineupSource: "effective",
    totalScore: 72.5,
    fantasyGoals: 2,
    starters: [
      {
        athleteId: "a1",
        name: "Portiere",
        role: "P",
        fantasyScore: 6.5,
        isEffectiveStarter: true,
        isBench: false,
      },
      {
        athleteId: "a2",
        name: "Attaccante",
        role: "A",
        fantasyScore: 8,
        isEffectiveStarter: true,
        isBench: false,
      },
    ],
    bench: [
      {
        athleteId: "a3",
        name: "Panchinaro",
        role: "C",
        fantasyScore: 6,
        isEffectiveStarter: false,
        isBench: true,
      },
    ],
  },
  away: {
    fantasyTeamId: "team-b",
    teamName: "Giulia United",
    displayName: "Giulia",
    module: "3-5-2",
    lineupSource: "effective",
    totalScore: 68,
    fantasyGoals: 1,
    starters: [
      {
        athleteId: "b1",
        name: "Portiere",
        role: "P",
        fantasyScore: 6,
        isEffectiveStarter: true,
        isBench: false,
      },
      {
        athleteId: "b2",
        name: "Centrocampista",
        role: "C",
        fantasyScore: 7,
        isEffectiveStarter: true,
        isBench: false,
      },
    ],
    bench: [],
  },
  result: {
    homeScore: 72.5,
    awayScore: 68,
    homeFantasyGoals: 2,
    awayFantasyGoals: 1,
    outcome: "home",
    resultFinal: false,
    computedAt: "2026-08-17T18:00:00.000Z",
  },
};

function toFormationSlots(players: H2HPlayerScore[]): FormationSlot[] {
  return players.map((player) => ({
    id: player.athleteId,
    label: player.fantasyScore !== null ? `${player.name} · ${player.fantasyScore.toFixed(1)}` : player.name,
    playerName:
      player.fantasyScore !== null
        ? `${player.name} · ${player.fantasyScore.toFixed(1)}`
        : player.name,
    role: player.role,
  }));
}

function SideBlock({ side, title }: { side: H2HSideLineup; title: string }) {
  const teamLabel = side.teamName ?? side.displayName;
  return (
    <section data-testid={`matchup-side-${title}`}>
      <h2>
        {teamLabel}
        {side.module ? ` · ${side.module}` : ""}
      </h2>
      <p>
        Punti: <strong>{side.totalScore !== null ? side.totalScore.toFixed(1) : "—"}</strong>
        {" · "}
        Gol fantasy: <strong>{side.fantasyGoals !== null ? side.fantasyGoals : "—"}</strong>
        {" · "}
        Fonte:{" "}
        {side.lineupSource === "effective"
          ? "formazione effettiva"
          : side.lineupSource === "submitted"
            ? "formazione schierata"
            : "non disponibile"}
      </p>
      {side.starters.length === 0 ? (
        <UiStatePanel
          state="empty"
          title="Formazione assente"
          message="Questa squadra non ha ancora una formazione per il turno."
          testId={`matchup-lineup-empty-${title}`}
        />
      ) : (
        <FormationView
          title={`Titolari — ${teamLabel}`}
          slots={toFormationSlots(side.starters)}
          bench={toFormationSlots(side.bench)}
          benchTitle="Panchina"
        />
      )}
    </section>
  );
}

function outcomeLabel(outcome: "home" | "away" | "draw" | null): string {
  if (outcome === "home") {
    return "Vittoria casa";
  }
  if (outcome === "away") {
    return "Vittoria trasferta";
  }
  if (outcome === "draw") {
    return "Pareggio";
  }
  return "Esito non disponibile";
}

/** Dettaglio scontro H2H: confronto formazioni + punteggi live. */
export function MatchupDetailPage() {
  const { isDemoMode, activeLeagueId, can } = useAuth();
  const { pathname, search } = useLocation();
  const demoState = isDemoMode ? parseWireframeStateFromSearch(search) : null;
  const slotId = pathname.startsWith("/turni/scontro/")
    ? pathname.slice("/turni/scontro/".length).split("/")[0] || null
    : null;

  const canView = can(["matchday:view"]);
  const [detail, setDetail] = useState<H2HMatchupDetail | null>(() =>
    isDemoMode && demoState === "success" ? DEMO_DETAIL : null,
  );
  const [loading, setLoading] = useState(() => (isDemoMode ? demoState === "loading" : true));
  const [error, setError] = useState<string | null>(() =>
    isDemoMode && demoState === "error" ? "Impossibile caricare lo scontro (demo)." : null,
  );

  const loadDetail = useCallback(async () => {
    if (isDemoMode) {
      if (demoState === "loading") {
        setLoading(true);
        return;
      }
      if (demoState === "error") {
        setLoading(false);
        setError("Impossibile caricare lo scontro (demo).");
        setDetail(null);
        return;
      }
      if (demoState === "empty") {
        setLoading(false);
        setError(null);
        setDetail(null);
        return;
      }
      setLoading(false);
      setError(null);
      setDetail(DEMO_DETAIL);
      return;
    }

    if (!activeLeagueId || !slotId) {
      setLoading(false);
      setDetail(null);
      setError(slotId ? null : "Scontro non specificato.");
      return;
    }

    const session = loadStoredSession();
    if (!session?.accessToken) {
      setLoading(false);
      setError("Sessione non disponibile. Accedi di nuovo.");
      return;
    }

    setLoading(true);
    setError(null);
    try {
      const next = await fetchH2HMatchup(session.accessToken, activeLeagueId, slotId);
      setDetail(next);
    } catch (err) {
      setError(getApiErrorMessage(err, "Impossibile caricare lo scontro."));
      setDetail(null);
    } finally {
      setLoading(false);
    }
  }, [activeLeagueId, demoState, isDemoMode, slotId]);

  useEffect(() => {
    void loadDetail();
  }, [loadDetail]);

  const { degraded: liveDegraded } = useLiveMatchupPolling(
    activeLeagueId,
    slotId,
    detail,
    setDetail,
    !isDemoMode,
  );

  const showForbidden = (isDemoMode && demoState === "forbidden") || !canView;

  return (
    <PageContainer
      title="Scontro diretto"
      header={
        <Breadcrumb
          items={[
            { label: "Leghe", href: "/leghe" },
            { label: "Turni", href: "/turni?tab=calendario" },
            { label: "Scontro" },
          ]}
        />
      }
    >
      <p>
        <Link to="/turni?tab=calendario" data-testid="matchup-back">
          ← Torna al calendario fantallenatori
        </Link>
      </p>

      {showForbidden ? (
        <UiStatePanel
          state="forbidden"
          title="Permessi insufficienti"
          message="Non hai accesso al dettaglio dello scontro."
          testId="matchup-forbidden"
        />
      ) : null}

      {!showForbidden && loading ? (
        <UiStatePanel
          state="loading"
          title="Caricamento scontro"
          message="Recupero formazioni e punteggi…"
          testId="matchup-loading"
        />
      ) : null}

      {!showForbidden && !loading && error ? (
        <div data-testid="matchup-error-wrap">
          <UiStatePanel
            state="error"
            title="Scontro non disponibile"
            message={error}
            testId="matchup-error"
          />
          <Button type="button" variant="secondary" onClick={() => void loadDetail()}>
            Ricarica
          </Button>
        </div>
      ) : null}

      {!showForbidden && !loading && !error && !detail ? (
        <UiStatePanel
          state="empty"
          title="Scontro non trovato"
          message="Lo scontro richiesto non è presente nel calendario confermato."
          testId="matchup-empty"
        />
      ) : null}

      {!showForbidden && !loading && !error && detail ? (
        <div className="fa-ds-showcase__stack" data-testid="matchup-detail">
          <p>
            Giornata {detail.roundNumber}
            {detail.live ? (
              <>
                {" · "}
                <Badge variant="warning" data-testid="matchup-live-badge">
                  Live
                </Badge>
              </>
            ) : null}
            {detail.result ? (
              <>
                {" · "}
                <Badge
                  variant={detail.result.resultFinal ? "success" : "warning"}
                  data-testid="matchup-result-status"
                >
                  {detail.result.resultFinal ? "Finale" : "Provvisorio"}
                </Badge>
              </>
            ) : null}
            {liveDegraded ? (
              <span data-testid="matchup-live-degraded"> · Aggiornamento live rallentato…</span>
            ) : null}
          </p>

          {detail.isBye ? (
            <UiStatePanel
              state="empty"
              title="Riposo"
              message={`${detail.home.teamName ?? detail.home.displayName} è a riposo in questa giornata.`}
              testId="matchup-bye"
            />
          ) : (
            <>
              <div data-testid="matchup-result-summary">
                <p>
                  <strong>{detail.home.teamName ?? detail.home.displayName}</strong>
                  {" "}
                  {detail.result?.homeFantasyGoals ?? "—"}–
                  {detail.result?.awayFantasyGoals ?? "—"}{" "}
                  <strong>{detail.away?.teamName ?? detail.away?.displayName ?? "Avversario"}</strong>
                </p>
                <p>
                  Punti {detail.home.totalScore?.toFixed(1) ?? "—"} –{" "}
                  {detail.away?.totalScore?.toFixed(1) ?? "—"}
                  {" · "}
                  {outcomeLabel(detail.result?.outcome ?? null)}
                </p>
              </div>
              <div className="fa-ds-showcase__row" style={{ alignItems: "flex-start" }}>
                <SideBlock side={detail.home} title="home" />
                {detail.away ? <SideBlock side={detail.away} title="away" /> : null}
              </div>
            </>
          )}
        </div>
      ) : null}
    </PageContainer>
  );
}
