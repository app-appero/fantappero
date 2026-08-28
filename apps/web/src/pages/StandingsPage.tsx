import type { LeagueStanding } from "@fantappero/contracts";
import { formatFantasyPoints } from "@fantappero/contracts";
import {
  Breadcrumb,
  Button,
  PageContainer,
  StandingsTable,
  type StandingsRow,
  UiStatePanel,
  WireframeSection,
} from "@fantappero/ui";
import { useCallback, useEffect, useMemo, useState } from "react";
import { fetchLeagueStandings, fetchMyFantasyTeam } from "../api/leagues";
import { getApiErrorMessage, useAuth } from "../auth/AuthContext";
import { loadStoredSession } from "../auth/sessionStorage";
import { useLocation } from "../router/simpleRouter";
import { WireframePage } from "../wireframes/WireframePage";
import { parseWireframeStateFromSearch } from "../wireframes/useWireframeState";

/**
 * I gol fantasy sono pochi per partita (0–3), i Fantapunti sono la somma dei
 * punti di formazione: la demo teneva valori da Fantapunti nel campo dei gol.
 */
const DEMO_STANDINGS: LeagueStanding[] = [
  {
    fantasyTeamId: "1",
    teamName: "Rivali FC",
    position: 1,
    played: 11,
    won: 7,
    drawn: 3,
    lost: 1,
    fantasyGoalsFor: 21,
    fantasyGoalsAgainst: 12,
    fantasyPointsFor: 820,
    fantasyPointsAgainst: 760,
    points: 24,
    computedAt: "2026-08-01T12:00:00.000Z",
  },
  {
    fantasyTeamId: "2",
    teamName: "La tua squadra",
    position: 2,
    played: 11,
    won: 6,
    drawn: 4,
    lost: 1,
    fantasyGoalsFor: 19,
    fantasyGoalsAgainst: 13,
    fantasyPointsFor: 798.5,
    fantasyPointsAgainst: 772,
    points: 22,
    computedAt: "2026-08-01T12:00:00.000Z",
  },
  {
    fantasyTeamId: "3",
    teamName: "Underdogs",
    position: 3,
    played: 11,
    won: 5,
    drawn: 4,
    lost: 2,
    fantasyGoalsFor: 16,
    fantasyGoalsAgainst: 17,
    fantasyPointsFor: 755,
    fantasyPointsAgainst: 780,
    points: 19,
    computedAt: "2026-08-01T12:00:00.000Z",
  },
];

const DEMO_MY_TEAM_ID = "2";

function toTableRows(
  standings: LeagueStanding[],
  myTeamId: string | null,
): StandingsRow[] {
  return standings.map((row) => {
    const isCurrentUser = myTeamId !== null && row.fantasyTeamId === myTeamId;
    return {
      id: row.fantasyTeamId,
      position: row.position,
      teamName: row.teamName,
      played: row.played,
      points: row.points,
      goalsFor: row.fantasyGoalsFor,
      goalsAgainst: row.fantasyGoalsAgainst,
      fantasyPointsFor: formatFantasyPoints(row.fantasyPointsFor),
      fantasyPointsAgainst: formatFantasyPoints(row.fantasyPointsAgainst),
      isCurrentUser,
      highlightLabel: isCurrentUser ? "Tu" : undefined,
    };
  });
}

function StandingsTableBlock({
  rows,
  testId = "standings-table",
}: {
  rows: StandingsRow[];
  testId?: string;
}) {
  return (
    <WireframeSection label="Ranking lega" testId="wireframe-region-standings">
      <StandingsTable
        caption="Classifica lega"
        positionLabel="Pos."
        teamLabel="Squadra"
        playedLabel="G"
        pointsLabel="Pt"
        goalsLabel="GF:GS"
        fantasyPointsLabel="FP:FS"
        rows={rows}
        testId={testId}
      />
    </WireframeSection>
  );
}

/** Classifica lega aggiornata dai risultati H2H (EP07-06). */
export function StandingsPage() {
  const { isDemoMode, activeLeagueId, activeLeague } = useAuth();
  const { search } = useLocation();
  const demoState = isDemoMode ? parseWireframeStateFromSearch(search) : null;

  const [standings, setStandings] = useState<LeagueStanding[]>(() =>
    isDemoMode && demoState !== "empty" && demoState !== "error" && demoState !== "loading"
      ? DEMO_STANDINGS
      : [],
  );
  const [myTeamId, setMyTeamId] = useState<string | null>(() =>
    isDemoMode && demoState === "success" ? DEMO_MY_TEAM_ID : null,
  );
  const [loading, setLoading] = useState(() => (isDemoMode ? demoState === "loading" : true));
  const [loadError, setLoadError] = useState<string | null>(() =>
    isDemoMode && demoState === "error" ? "Impossibile caricare la classifica (demo)." : null,
  );

  const loadStandings = useCallback(async () => {
    if (isDemoMode) {
      if (demoState === "loading") {
        setLoading(true);
        setStandings([]);
        setMyTeamId(null);
        setLoadError(null);
        return;
      }
      if (demoState === "error") {
        setLoading(false);
        setStandings([]);
        setMyTeamId(null);
        setLoadError("Impossibile caricare la classifica (demo).");
        return;
      }
      if (demoState === "empty" || demoState === "forbidden") {
        setLoading(false);
        setStandings([]);
        setMyTeamId(null);
        setLoadError(null);
        return;
      }
      setStandings(DEMO_STANDINGS);
      setMyTeamId(DEMO_MY_TEAM_ID);
      setLoading(false);
      setLoadError(null);
      return;
    }

    if (!activeLeagueId) {
      setLoading(false);
      setStandings([]);
      setMyTeamId(null);
      setLoadError(null);
      return;
    }

    const stored = loadStoredSession();
    if (!stored?.accessToken) {
      setLoading(false);
      setLoadError("Sessione non disponibile. Accedi di nuovo.");
      return;
    }

    setLoading(true);
    setLoadError(null);
    try {
      const [rows, myTeam] = await Promise.all([
        fetchLeagueStandings(stored.accessToken, activeLeagueId),
        fetchMyFantasyTeam(stored.accessToken, activeLeagueId).catch(() => null),
      ]);
      setStandings(rows);
      setMyTeamId(myTeam?.id ?? null);
    } catch (error) {
      setLoadError(getApiErrorMessage(error, "Impossibile caricare la classifica."));
      setStandings([]);
      setMyTeamId(null);
    } finally {
      setLoading(false);
    }
  }, [activeLeagueId, demoState, isDemoMode]);

  useEffect(() => {
    void loadStandings();
  }, [loadStandings]);

  const rows = useMemo(() => toTableRows(standings, myTeamId), [myTeamId, standings]);
  const computedAt = standings[0]?.computedAt ?? null;

  if (isDemoMode) {
    return (
      <PageContainer
        title="Classifica"
        density="compact"
        header={
          <Breadcrumb
            items={[
              { label: "Leghe", href: "/leghe" },
              { label: "Classifica" },
            ]}
          />
        }
      >
        <WireframePage
          screenId="standings"
          successContent={<StandingsTableBlock rows={rows} />}
        />
      </PageContainer>
    );
  }

  return (
    <PageContainer
      title="Classifica"
      density="compact"
      header={
        <Breadcrumb
          items={[
            { label: "Leghe", href: "/leghe" },
            { label: activeLeague?.name ?? "Classifica" },
          ]}
        />
      }
    >
      {loading ? (
        <UiStatePanel
          state="loading"
          title="Caricamento classifica"
          message="Recupero posizione, punti e gol fantasy…"
          testId="standings-loading"
        />
      ) : null}

      {!loading && loadError ? (
        <div>
          <UiStatePanel
            state="error"
            title="Classifica non disponibile"
            message={loadError}
            testId="standings-error"
          />
          <Button type="button" variant="ghost" onClick={() => void loadStandings()}>
            Riprova
          </Button>
        </div>
      ) : null}

      {!loading && !loadError && !activeLeagueId ? (
        <UiStatePanel
          state="empty"
          title="Nessuna lega selezionata"
          message="Seleziona una lega dall'elenco per vedere la classifica."
          testId="standings-no-league"
        />
      ) : null}

      {!loading && !loadError && activeLeagueId && standings.length === 0 ? (
        <UiStatePanel
          state="empty"
          title="Classifica non ancora disponibile"
          message="La classifica si aggiorna automaticamente quando i risultati dei turni diventano finali."
          testId="standings-empty"
        />
      ) : null}

      {!loading && !loadError && standings.length > 0 ? (
        <div data-testid="standings-success">
          {computedAt ? (
            <p>
              Aggiornata:{" "}
              {new Intl.DateTimeFormat("it-IT", {
                dateStyle: "medium",
                timeStyle: "short",
                timeZone: "Europe/Rome",
              }).format(new Date(computedAt))}
            </p>
          ) : null}
          <StandingsTableBlock rows={rows} />
        </div>
      ) : null}
    </PageContainer>
  );
}
