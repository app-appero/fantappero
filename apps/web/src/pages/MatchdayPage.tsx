import type {
  AiLineupRun,
  FantasyTurnDetail,
  FantasyTurnFixture,
  FantasyTurnSummary,
  H2HCalendar,
  PendingFixtureSummary,
} from "@fantappero/contracts";
import {
  TURN_DISPLAY_LABEL,
  mapFixtureMatchStatus,
  resolveDefaultEuropeanTurn,
  resolveTurnDisplayStates,
} from "@fantappero/contracts";
import {
  Badge,
  Breadcrumb,
  Button,
  Card,
  CardBody,
  CardHeader,
  MatchCard,
  PageContainer,
  Select,
  Tab,
  TabList,
  TabPanel,
  Tabs,
  UiStatePanel,
} from "@fantappero/ui";
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  excludeFantasyTurnFixture,
  fetchFantasyTurn,
  fetchFantasyTurns,
  fetchH2HCalendar,
  fetchPendingFixtures,
  openFantasyTurn,
  recalculateFantasyTurnCutoff,
  refreshFullCalendar,
  runAiLineups,
} from "../api/leagues";
import { getApiErrorMessage, useAuth } from "../auth/AuthContext";
import { loadStoredSession } from "../auth/sessionStorage";
import { useLiveH2HPolling } from "../matchday/useLiveH2HPolling";
import { useLiveTurnPolling } from "../matchday/useLiveTurnPolling";
import { Link, useLocation } from "../router/simpleRouter";
import { parseWireframeStateFromSearch } from "../wireframes/useWireframeState";
import { MatchdayH2HPanel } from "./MatchdayH2HPanel";

const MATCH_STATUS_LABEL: Record<string, string> = {
  scheduled: "In programma",
  live: "In corso",
  finished: "Terminata",
  postponed: "Rinviata",
  needs_update: "Da aggiornare",
};

/** Etichetta di stato per la card lista: include il minuto quando la partita è live. */
function matchCardStatusLabel(fixture: FantasyTurnFixture): string {
  const mapped = mapFixtureMatchStatus(fixture.statusShort, fixture.kickoffAt);
  const base = MATCH_STATUS_LABEL[mapped] ?? fixture.statusShort;
  if (mapped === "live" && fixture.statusElapsed !== null) {
    return `${base} · ${fixture.statusElapsed}'`;
  }
  return base;
}

const DEMO_TURN: FantasyTurnDetail = {
  id: "turn-demo-1",
  leagueId: "lega-demo",
  number: 1,
  kind: "weekend",
  windowStartAt: "2026-08-14T22:00:00.000Z",
  windowEndAt: "2026-08-18T22:00:00.000Z",
  opensAt: null,
  closesAt: null,
  cutoffAt: "2026-08-15T14:00:00.000Z",
  status: "scheduled",
  effectiveStatus: "scheduled",
  skipReason: null,
  fixtureCount: 2,
  generatedAt: "2026-08-12T08:00:00.000Z",
  modificationAllowed: true,
  matchStatus: "scheduled",
  homologationStatus: "provisional",
  fixtures: [
    {
      id: "rf-1",
      fixtureId: "fx-1",
      includedReason: "window",
      excludedAt: null,
      kickoffAt: "2026-08-15T14:00:00.000Z",
      observedKickoffAt: "2026-08-15T14:00:00.000Z",
      lockLatchedAt: "2026-08-15T14:00:00.000Z",
      statusShort: "PST",
      statusElapsed: null,
      homeGoals: null,
      awayGoals: null,
      homeClubName: "West Ham",
      awayClubName: "Chelsea",
      homeClubLogoUrl: null,
      awayClubLogoUrl: null,
      competitionName: "Premier League",
      providerId: 1035055,
      updatedAt: "2026-08-15T13:55:00.000Z",
      feedState: "fresh",
      feedStateLabel: "Aggiornato",
    },
    {
      id: "rf-2",
      fixtureId: "fx-2",
      includedReason: "window",
      excludedAt: null,
      kickoffAt: "2026-08-15T18:30:00.000Z",
      observedKickoffAt: "2026-08-15T18:30:00.000Z",
      lockLatchedAt: null,
      statusShort: "NS",
      statusElapsed: null,
      homeGoals: null,
      awayGoals: null,
      homeClubName: "Inter",
      awayClubName: "Milan",
      homeClubLogoUrl: null,
      awayClubLogoUrl: null,
      competitionName: "Serie A",
      providerId: 1035056,
      updatedAt: null,
      feedState: "unavailable",
      feedStateLabel: "Dati non disponibili",
    },
  ],
};

function formatDateTime(value: string | null): string {
  if (!value) {
    return "—";
  }
  try {
    return new Intl.DateTimeFormat("it-IT", {
      dateStyle: "medium",
      timeStyle: "short",
      timeZone: "Europe/Rome",
    }).format(new Date(value));
  } catch {
    return value;
  }
}

function resolveMatchdayTab(raw: string | null): "calendario" | "europei" {
  if (raw === "europei" || raw === "turno") {
    return "europei";
  }
  return "calendario";
}

function groupFixturesByCompetition(fixtures: FantasyTurnDetail["fixtures"]) {
  const groups = new Map<string, FantasyTurnDetail["fixtures"]>();
  for (const fixture of fixtures) {
    const key = fixture.competitionName ?? "Altre competizioni";
    const bucket = groups.get(key);
    if (bucket) {
      bucket.push(fixture);
    } else {
      groups.set(key, [fixture]);
    }
  }
  return [...groups.entries()];
}

const DEMO_H2H: H2HCalendar = {
  id: "demo-h2h",
  leagueId: "lega-demo",
  status: "confirmed",
  format: "single_round_robin",
  algorithmVersion: "circle_rr_v1",
  participantCount: 4,
  roundCount: 3,
  matchupCount: 6,
  byeCount: 0,
  generatedAt: "2026-08-12T08:00:00.000Z",
  confirmedAt: "2026-08-12T09:00:00.000Z",
  live: true,
  summary: { message: "Calendario demo." },
  rounds: [
    {
      roundNumber: 1,
      fantasyRoundId: "turn-demo-0",
      homologationStatus: "homologated",
      europeanTurnStatus: "locked",
      beforeLeagueCreation: false,
      matchups: [
        {
          slotId: "slot-demo-past",
          slotIndex: 0,
          isBye: false,
          homeUserId: "a",
          homeDisplayName: "Marco",
          homeTeamName: "Marco FC",
          awayUserId: "d",
          awayDisplayName: "Sara",
          awayTeamName: "Sara City",
          result: {
            homeScore: 70,
            awayScore: 66,
            homeFantasyGoals: 1,
            awayFantasyGoals: 1,
            outcome: "draw",
            resultFinal: true,
            computedAt: "2026-08-10T18:00:00.000Z",
          },
        },
        {
          slotId: "slot-demo-past-2",
          slotIndex: 1,
          isBye: false,
          homeUserId: "b",
          homeDisplayName: "Giulia",
          homeTeamName: "Giulia United",
          awayUserId: "c",
          awayDisplayName: "Luca",
          awayTeamName: "Luca XI",
          result: {
            homeScore: 74,
            awayScore: 61,
            homeFantasyGoals: 2,
            awayFantasyGoals: 0,
            outcome: "home",
            resultFinal: true,
            computedAt: "2026-08-10T18:00:00.000Z",
          },
        },
      ],
    },
    {
      roundNumber: 2,
      fantasyRoundId: "turn-demo-1",
      homologationStatus: "provisional",
      europeanTurnStatus: "open",
      beforeLeagueCreation: false,
      matchups: [
        {
          slotId: "slot-demo-1",
          slotIndex: 0,
          isBye: false,
          homeUserId: "a",
          homeDisplayName: "Marco",
          homeTeamName: "Marco FC",
          awayUserId: "b",
          awayDisplayName: "Giulia",
          awayTeamName: "Giulia United",
          result: {
            homeScore: 72.5,
            awayScore: 68,
            homeFantasyGoals: 2,
            awayFantasyGoals: 1,
            outcome: "home",
            resultFinal: false,
            computedAt: "2026-08-17T18:00:00.000Z",
          },
        },
        {
          slotId: "slot-demo-2",
          slotIndex: 1,
          isBye: true,
          homeUserId: "c",
          homeDisplayName: "Luca",
          homeTeamName: "Luca XI",
          awayUserId: null,
          awayDisplayName: null,
          awayTeamName: null,
          result: null,
        },
      ],
    },
    {
      roundNumber: 3,
      fantasyRoundId: null,
      homologationStatus: null,
      europeanTurnStatus: null,
      beforeLeagueCreation: false,
      matchups: [
        {
          slotId: "slot-demo-3",
          slotIndex: 0,
          isBye: false,
          homeUserId: "a",
          homeDisplayName: "Marco",
          homeTeamName: "Marco FC",
          awayUserId: "c",
          awayDisplayName: "Luca",
          awayTeamName: "Luca XI",
          result: null,
        },
        {
          slotId: "slot-demo-4",
          slotIndex: 1,
          isBye: false,
          homeUserId: "b",
          homeDisplayName: "Giulia",
          homeTeamName: "Giulia United",
          awayUserId: "d",
          awayDisplayName: "Sara",
          awayTeamName: "Sara City",
          result: null,
        },
      ],
    },
  ],
};

/** Turni — calendario H2H fantallenatori e turni europei. */
export function MatchdayPage() {
  const { isDemoMode, activeLeagueId, can } = useAuth();
  const { search } = useLocation();
  const demoState = isDemoMode ? parseWireframeStateFromSearch(search) : null;
  const params = new URLSearchParams(search.startsWith("?") ? search.slice(1) : search);
  const initialTab = resolveMatchdayTab(params.get("tab"));
  const [tab, setTab] = useState(initialTab);

  const [h2hCalendar, setH2hCalendar] = useState<H2HCalendar | null>(() => {
    if (isDemoMode && demoState === "success") {
      return DEMO_H2H;
    }
    return null;
  });
  const [h2hLoading, setH2hLoading] = useState(() => {
    if (isDemoMode) {
      return demoState === "loading";
    }
    return true;
  });
  const [h2hError, setH2hError] = useState<string | null>(() => {
    if (isDemoMode && demoState === "error") {
      return "Impossibile caricare il calendario H2H (demo).";
    }
    return null;
  });

  const [turns, setTurns] = useState<FantasyTurnSummary[]>(() => {
    if (isDemoMode && demoState === "success") {
      return [DEMO_TURN];
    }
    return [];
  });
  const [selected, setSelected] = useState<FantasyTurnDetail | null>(() => {
    if (isDemoMode && demoState === "success") {
      return DEMO_TURN;
    }
    return null;
  });

  // Stato mostrato all'utente: dipende da dove cade il turno rispetto ad
  // adesso, non dallo stato interno del ciclo di vita formazioni.
  const turnDisplayStates = useMemo(() => resolveTurnDisplayStates(turns), [turns]);
  const selectedDisplayState = useMemo(() => {
    const index = turns.findIndex((turn) => turn.id === selected?.id);
    return index >= 0 ? (turnDisplayStates[index] ?? "upcoming") : "upcoming";
  }, [turns, turnDisplayStates, selected?.id]);
  const [pendingFixtures, setPendingFixtures] = useState<PendingFixtureSummary[]>([]);
  const [loading, setLoading] = useState(() => {
    if (isDemoMode) {
      return demoState === "loading";
    }
    return true;
  });
  const [busy, setBusy] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(() => {
    if (isDemoMode && demoState === "error") {
      return "Impossibile caricare i turni (demo).";
    }
    return null;
  });
  const [actionError, setActionError] = useState<string | null>(null);
  const [actionMessage, setActionMessage] = useState<string | null>(null);
  const [aiLineupBusy, setAiLineupBusy] = useState(false);
  const [aiLineupRun, setAiLineupRun] = useState<AiLineupRun | null>(null);
  const [aiLineupError, setAiLineupError] = useState<string | null>(null);
  const [refreshingCalendar, setRefreshingCalendar] = useState(false);
  const [calendarRefreshProgress, setCalendarRefreshProgress] = useState<{
    percent: number;
    stage: string;
    message: string;
  } | null>(null);
  const [calendarRefreshError, setCalendarRefreshError] = useState<string | null>(null);
  const [calendarRefreshSuccess, setCalendarRefreshSuccess] = useState<string | null>(null);

  const isAdmin = can(["league:admin"]);
  const canView = can(["matchday:view"]);

  const showForbidden = useMemo(() => {
    if (isDemoMode && demoState === "forbidden") {
      return true;
    }
    return !canView;
  }, [canView, demoState, isDemoMode]);

  const loadH2H = useCallback(async () => {
    if (isDemoMode) {
      if (demoState === "loading") {
        setH2hLoading(true);
        return;
      }
      if (demoState === "error") {
        setH2hLoading(false);
        setH2hError("Impossibile caricare il calendario H2H (demo).");
        setH2hCalendar(null);
        return;
      }
      if (demoState === "empty") {
        setH2hLoading(false);
        setH2hError(null);
        setH2hCalendar(null);
        return;
      }
      setH2hLoading(false);
      setH2hError(null);
      setH2hCalendar(DEMO_H2H);
      return;
    }

    if (!activeLeagueId) {
      setH2hLoading(false);
      setH2hCalendar(null);
      setH2hError(null);
      return;
    }

    const session = loadStoredSession();
    if (!session?.accessToken) {
      setH2hLoading(false);
      setH2hError("Sessione non disponibile. Accedi di nuovo.");
      return;
    }

    setH2hLoading(true);
    setH2hError(null);
    try {
      const calendar = await fetchH2HCalendar(session.accessToken, activeLeagueId);
      setH2hCalendar(calendar);
    } catch (error) {
      setH2hError(getApiErrorMessage(error, "Impossibile caricare il calendario H2H."));
      setH2hCalendar(null);
    } finally {
      setH2hLoading(false);
    }
  }, [activeLeagueId, demoState, isDemoMode]);

  const loadTurns = useCallback(async () => {
    if (isDemoMode) {
      if (demoState === "loading") {
        setLoading(true);
        return;
      }
      if (demoState === "error") {
        setLoading(false);
        setLoadError("Impossibile caricare i turni (demo).");
        setTurns([]);
        setSelected(null);
        return;
      }
      if (demoState === "empty") {
        setLoading(false);
        setLoadError(null);
        setTurns([]);
        setSelected(null);
        return;
      }
      setLoading(false);
      setLoadError(null);
      setTurns([DEMO_TURN]);
      setSelected(DEMO_TURN);
      return;
    }

    if (!activeLeagueId) {
      setLoading(false);
      setTurns([]);
      setSelected(null);
      setLoadError(null);
      return;
    }

    const session = loadStoredSession();
    if (!session?.accessToken) {
      setLoading(false);
      setLoadError("Sessione non disponibile. Accedi di nuovo.");
      return;
    }

    setLoading(true);
    setLoadError(null);
    try {
      const list = await fetchFantasyTurns(session.accessToken, activeLeagueId);
      setTurns(list);
      const defaultTurn = resolveDefaultEuropeanTurn(list);
      if (!defaultTurn) {
        setSelected(null);
      } else {
        const detail = await fetchFantasyTurn(session.accessToken, activeLeagueId, defaultTurn.id);
        setSelected(detail);
      }
    } catch (error) {
      setLoadError(getApiErrorMessage(error, "Impossibile caricare i turni."));
      setTurns([]);
      setSelected(null);
    } finally {
      setLoading(false);
    }
  }, [activeLeagueId, demoState, isDemoMode]);

  const loadPendingFixtures = useCallback(async () => {
    if (isDemoMode || !activeLeagueId) {
      setPendingFixtures([]);
      return;
    }
    const session = loadStoredSession();
    if (!session?.accessToken) {
      return;
    }
    try {
      const list = await fetchPendingFixtures(session.accessToken, activeLeagueId);
      setPendingFixtures(list);
    } catch {
      // Non bloccante: la sezione "da aggiornare" è puramente informativa.
      setPendingFixtures([]);
    }
  }, [activeLeagueId, isDemoMode]);

  useEffect(() => {
    void loadH2H();
  }, [loadH2H]);

  useEffect(() => {
    void loadTurns();
  }, [loadTurns]);

  useEffect(() => {
    void loadPendingFixtures();
  }, [loadPendingFixtures]);

  const { degraded: liveUpdateDegraded } = useLiveTurnPolling(
    activeLeagueId,
    selected,
    setSelected,
    !isDemoMode && tab === "europei",
  );

  const { degraded: h2hLiveDegraded } = useLiveH2HPolling(
    activeLeagueId,
    h2hCalendar,
    setH2hCalendar,
    !isDemoMode && tab === "calendario",
  );

  async function selectTurn(turnId: string) {
    if (isDemoMode) {
      setSelected(DEMO_TURN);
      return;
    }
    const session = loadStoredSession();
    if (!session?.accessToken || !activeLeagueId) {
      return;
    }
    setBusy(true);
    setActionError(null);
    try {
      const detail = await fetchFantasyTurn(session.accessToken, activeLeagueId, turnId);
      setSelected(detail);
    } catch (error) {
      setActionError(getApiErrorMessage(error, "Dettaglio turno non disponibile."));
    } finally {
      setBusy(false);
    }
  }

  async function runRefreshCalendar() {
    if (isDemoMode) {
      setCalendarRefreshSuccess("Calendario aggiornato (demo).");
      setSelected(DEMO_TURN);
      setTurns([DEMO_TURN]);
      return;
    }
    const session = loadStoredSession();
    if (!session?.accessToken || !activeLeagueId) {
      return;
    }
    setRefreshingCalendar(true);
    setCalendarRefreshError(null);
    setCalendarRefreshSuccess(null);
    setCalendarRefreshProgress({ percent: 0, stage: "queued", message: "Avvio in corso…" });
    try {
      const result = await refreshFullCalendar(session.accessToken, activeLeagueId, {
        onProgress: (progress) =>
          setCalendarRefreshProgress({
            percent: progress.percent,
            stage: progress.stage,
            message: progress.message,
          }),
      });
      setCalendarRefreshSuccess(result.message);
      await loadTurns();
      await loadPendingFixtures();
    } catch (error) {
      setCalendarRefreshError(getApiErrorMessage(error, "Aggiornamento calendario non riuscito."));
    } finally {
      setRefreshingCalendar(false);
      setCalendarRefreshProgress(null);
    }
  }

  async function runOpen() {
    if (!selected) {
      return;
    }
    if (isDemoMode) {
      setSelected({ ...selected, status: "open", effectiveStatus: "open", opensAt: new Date().toISOString(), modificationAllowed: false });
      setActionMessage("Turno aperto (demo).");
      return;
    }
    const session = loadStoredSession();
    if (!session?.accessToken || !activeLeagueId) {
      return;
    }
    setBusy(true);
    setActionError(null);
    try {
      const detail = await openFantasyTurn(session.accessToken, activeLeagueId, selected.id);
      setSelected(detail);
      setActionMessage(`Turno ${detail.number} aperto.`);
      await loadTurns();
    } catch (error) {
      setActionError(getApiErrorMessage(error, "Apertura turno non riuscita."));
    } finally {
      setBusy(false);
    }
  }

  async function runExclude(fixtureId: string) {
    if (!selected) {
      return;
    }
    if (isDemoMode) {
      setSelected({
        ...selected,
        fixtureCount: Math.max(0, selected.fixtureCount - 1),
        fixtures: selected.fixtures.filter((row) => row.fixtureId !== fixtureId),
      });
      setActionMessage("Partita esclusa (demo).");
      return;
    }
    const session = loadStoredSession();
    if (!session?.accessToken || !activeLeagueId) {
      return;
    }
    setBusy(true);
    setActionError(null);
    try {
      const detail = await excludeFantasyTurnFixture(session.accessToken, activeLeagueId, selected.id, {
        fixtureId,
      });
      setSelected(detail);
      setActionMessage("Partita esclusa dal turno.");
      await loadTurns();
    } catch (error) {
      setActionError(getApiErrorMessage(error, "Esclusione non consentita."));
    } finally {
      setBusy(false);
    }
  }

  async function runRecalculate() {
    if (!selected) {
      return;
    }
    if (isDemoMode) {
      setActionMessage("Cutoff ricalcolato (demo).");
      return;
    }
    const session = loadStoredSession();
    if (!session?.accessToken || !activeLeagueId) {
      return;
    }
    setBusy(true);
    setActionError(null);
    try {
      const detail = await recalculateFantasyTurnCutoff(
        session.accessToken,
        activeLeagueId,
        selected.id,
      );
      setSelected(detail);
      setActionMessage("Cutoff aggiornato dagli orari correnti.");
    } catch (error) {
      setActionError(getApiErrorMessage(error, "Ricalcolo cutoff non riuscito."));
    } finally {
      setBusy(false);
    }
  }

  async function generateAiLineups(roundId: string) {
    if (isDemoMode) {
      setAiLineupRun({
        roundId,
        algorithmVersion: "ai_lineup_v1",
        dryRun: false,
        teams: [],
        summary: "Formazioni AI gestite: 0/0 nella lega demo",
      });
      return;
    }
    const session = loadStoredSession();
    if (!session?.accessToken || !activeLeagueId) {
      return;
    }
    setAiLineupBusy(true);
    setAiLineupError(null);
    try {
      setAiLineupRun(await runAiLineups(session.accessToken, activeLeagueId, roundId, false));
      await loadH2H();
    } catch (error) {
      setAiLineupError(getApiErrorMessage(error, "Generazione delle formazioni AI non riuscita."));
    } finally {
      setAiLineupBusy(false);
    }
  }

  return (
    <PageContainer
      title="Turni"
      header={
        <Breadcrumb
          items={[
            { label: "Leghe", href: "/leghe" },
            { label: "Turni" },
          ]}
        />
      }
    >
      {showForbidden ? (
        <UiStatePanel
          state="forbidden"
          title="Permessi insufficienti"
          message="Non hai accesso alla consultazione dei turni."
          testId="matchday-forbidden"
        />
      ) : null}

      {!showForbidden && !activeLeagueId && !isDemoMode ? (
        <UiStatePanel
          state="empty"
          title="Nessuna lega attiva"
          message="Seleziona una lega per consultare calendario e turni."
          testId="matchday-no-league"
        />
      ) : null}

      {!showForbidden && (activeLeagueId || isDemoMode) ? (
        <>
          {isAdmin ? (
            <Card data-testid="matchday-admin">
              <CardHeader title="Calendario della lega" />
              <CardBody>
                <p>
                  Recupera dal provider le partite dei campionati scelti, ne ricava i Turni
                  Europei validi della stagione e genera da quelli le giornate dei
                  fantallenatori. Le due sezioni restano sempre allineate.
                </p>
                <div className="fa-ds-showcase__row">
                  <Button
                    type="button"
                    loading={refreshingCalendar}
                    disabled={refreshingCalendar}
                    onClick={() => void runRefreshCalendar()}
                    data-testid="matchday-refresh-calendar"
                  >
                    Genera calendario
                  </Button>
                </div>
                {refreshingCalendar ? (
                  <UiStatePanel
                    state="loading"
                    title="Generazione in corso"
                    message={
                      calendarRefreshProgress
                        ? `${calendarRefreshProgress.message} (${calendarRefreshProgress.percent}%)`
                        : "Avvio in corso…"
                    }
                    testId="matchday-refresh-progress"
                  />
                ) : null}
                {!refreshingCalendar && calendarRefreshError ? (
                  <UiStatePanel
                    state="error"
                    title="Generazione non riuscita"
                    message={calendarRefreshError}
                    testId="matchday-refresh-error"
                  />
                ) : null}
                {!refreshingCalendar && calendarRefreshSuccess ? (
                  <UiStatePanel
                    state="success"
                    title="Calendario generato"
                    message={calendarRefreshSuccess}
                    testId="matchday-refresh-success"
                  />
                ) : null}
              </CardBody>
            </Card>
          ) : null}

          <Tabs value={tab} onValueChange={(value) => setTab(resolveMatchdayTab(value))}>
          <TabList aria-label="Sezioni turni">
            <Tab value="calendario">Calendario fantallenatori</Tab>
            <Tab value="europei">Turni europei</Tab>
          </TabList>
          <TabPanel value="calendario">
            <MatchdayH2HPanel
              calendar={h2hCalendar}
              loading={h2hLoading}
              error={h2hError}
              liveDegraded={h2hLiveDegraded}
              canAdmin={isAdmin}
              aiLineupBusy={aiLineupBusy}
              aiLineupRun={aiLineupRun}
              aiLineupError={aiLineupError}
              onGenerateAiLineups={(roundId) => void generateAiLineups(roundId)}
              onRetry={() => void loadH2H()}
            />
          </TabPanel>
          <TabPanel value="europei">

            {loading ? (
              <UiStatePanel
                state="loading"
                title="Caricamento turni"
                message="Recupero del calendario europeo in corso…"
                testId="matchday-loading"
              />
            ) : null}

            {!loading && loadError ? (
              <div data-testid="matchday-error-wrap">
                <UiStatePanel
                  state="error"
                  title="Turni non disponibili"
                  message={loadError}
                  testId="matchday-error"
                />
                <Button type="button" variant="secondary" onClick={() => void loadTurns()}>
                  Ricarica
                </Button>
              </div>
            ) : null}

            {!loading && !loadError && turns.length === 0 ? (
              <UiStatePanel
                state="empty"
                title="Nessun turno ancora"
                message="Un turno esiste solo se ogni fantallenatore può schierare la formazione con i giocatori della propria rosa. Finché le rose non sono assegnate (asta non ancora svolta) il calendario resta vuoto: si popolerà da solo subito dopo."
                testId="matchday-empty"
              />
            ) : null}

            {!loading && !loadError && turns.length > 0 ? (
              <div className="fa-matchday-europei" data-testid="matchday-turn-list">
                <div className="fa-matchday-toolbar">
                  <Select
                    label="Turno europeo"
                    options={turns.map((turn, index) => ({
                      value: turn.id,
                      label: `Turno ${turn.number} — ${TURN_DISPLAY_LABEL[turnDisplayStates[index] ?? "upcoming"]}`,
                    }))}
                    value={selected?.id ?? ""}
                    onChange={(event) => void selectTurn(event.target.value)}
                    data-testid="matchday-turn-select"
                  />
                </div>
              </div>
            ) : null}

            {!loading && !loadError && selected ? (
              <div className="fa-matchday-europei-detail" data-testid="matchday-turn-detail">
                <header className="fa-matchday-round__header">
                  <div>
                    <h2>Turno {selected.number}</h2>
                    <p className="fa-matchday-lede">
                      Stato: <strong>{TURN_DISPLAY_LABEL[selectedDisplayState]}</strong>
                    </p>
                    <p className="fa-matchday-hint">
                      Finestra {formatDateTime(selected.windowStartAt)} →{" "}
                      {formatDateTime(selected.windowEndAt)} · Cutoff{" "}
                      {formatDateTime(selected.cutoffAt)}
                    </p>
                  </div>
                  <div className="fa-matchday-toolbar__badges">
                    <Badge
                      variant={
                        selected.homologationStatus === "homologated" ? "success" : "warning"
                      }
                      data-testid="matchday-homologation-status"
                    >
                      {selected.homologationStatus === "homologated" ? "Finale" : "Provvisorio"}
                    </Badge>
                    {liveUpdateDegraded ? (
                      <span data-testid="matchday-live-degraded" className="fa-matchday-degraded">
                        Aggiornamento live rallentato…
                      </span>
                    ) : null}
                  </div>
                </header>

                {selected.fixtures.some((fixture) => fixture.lockLatchedAt) ? (
                  <p data-testid="matchday-cutoff-latch" className="fa-matchday-hint">
                    Un rinvio o un cambio orario non sblocca le partite il cui kickoff originale è
                    già trascorso. Le mosse tattiche già usate restano consumate.
                  </p>
                ) : null}
                {selected.skipReason ? <p>{selected.skipReason}</p> : null}

                <div className="fa-ds-showcase__row">
                  {isAdmin && selected.status === "scheduled" ? (
                    <Button
                      type="button"
                      disabled={busy}
                      onClick={() => void runOpen()}
                      data-testid="matchday-open"
                    >
                      Apri turno
                    </Button>
                  ) : null}
                  {isAdmin && selected.status !== "skipped" ? (
                    <Button
                      type="button"
                      variant="secondary"
                      disabled={busy}
                      onClick={() => void runRecalculate()}
                      data-testid="matchday-recalc"
                    >
                      Ricalcola cutoff
                    </Button>
                  ) : null}
                </div>

                <div className="fa-matchday-competitions" data-testid="matchday-fixtures">
                  {groupFixturesByCompetition(selected.fixtures).map(
                    ([competitionName, fixtures]) => (
                      <section
                        key={competitionName}
                        className="fa-matchday-competition"
                        data-testid={`matchday-competition-${competitionName}`}
                      >
                        <h3 className="fa-matchday-competition__title">{competitionName}</h3>
                        <div className="fa-matchday-competition__fixtures">
                          {fixtures.map((fixture) => (
                            <div key={fixture.id} className="fa-matchday-fixture">
                              <Link
                                to={`/turni/${selected.id}/partite/${fixture.fixtureId}`}
                                className="fa-matchday-matchup-link"
                                data-testid={`matchday-fixture-link-${fixture.fixtureId}`}
                                aria-label={`${fixture.homeClubName} contro ${fixture.awayClubName}, dettaglio partita`}
                              >
                                <MatchCard
                                  homeTeam={fixture.homeClubName}
                                  awayTeam={fixture.awayClubName}
                                  kickoffLabel={formatDateTime(fixture.kickoffAt)}
                                  status={mapFixtureMatchStatus(fixture.statusShort, fixture.kickoffAt)}
                                  statusLabel={matchCardStatusLabel(fixture)}
                                  homeLogoUrl={fixture.homeClubLogoUrl}
                                  awayLogoUrl={fixture.awayClubLogoUrl}
                                  score={
                                    fixture.homeGoals !== null && fixture.awayGoals !== null
                                      ? { home: fixture.homeGoals, away: fixture.awayGoals }
                                      : null
                                  }
                                />
                              </Link>
                              <p
                                className="fa-matchday-hint"
                                data-testid={`matchday-fixture-feed-${fixture.fixtureId}`}
                              >
                                {fixture.feedStateLabel}
                                {fixture.updatedAt
                                  ? ` · ultimo aggiornamento ${formatDateTime(fixture.updatedAt)}`
                                  : ""}
                              </p>
                              {fixture.lockLatchedAt ? (
                                <p
                                  className="fa-matchday-hint"
                                  data-testid={`matchday-lock-latched-${fixture.fixtureId}`}
                                >
                                  Bloccata: l'orario originale è già trascorso.
                                </p>
                              ) : null}
                              {isAdmin && selected.modificationAllowed ? (
                                <Button
                                  type="button"
                                  variant="ghost"
                                  disabled={busy}
                                  onClick={() => void runExclude(fixture.fixtureId)}
                                  data-testid={`matchday-exclude-${fixture.fixtureId}`}
                                >
                                  Escludi
                                </Button>
                              ) : null}
                            </div>
                          ))}
                        </div>
                      </section>
                    ),
                  )}
                </div>
              </div>
            ) : null}

            {pendingFixtures.length > 0 ? (
              <Card data-testid="matchday-pending-fixtures">
                <CardHeader title="Partite da aggiornare" />
                <CardBody>
                  <p>
                    Il provider conosce già competizione e squadre di queste partite, ma non
                    ancora data e ora definitive: verranno inserite automaticamente in un turno
                    non appena pubblicate.
                  </p>
                  <ul className="fa-matchday-pending-list">
                    {pendingFixtures.map((fixture) => (
                      <li key={fixture.fixtureId} data-testid={`pending-fixture-${fixture.fixtureId}`}>
                        {fixture.homeClubName} – {fixture.awayClubName}
                        {fixture.competitionName ? ` · ${fixture.competitionName}` : ""}
                        {fixture.roundLabel ? ` · ${fixture.roundLabel}` : ""}
                      </li>
                    ))}
                  </ul>
                </CardBody>
              </Card>
            ) : null}

            {actionMessage ? <p data-testid="matchday-success">{actionMessage}</p> : null}
            {actionError ? (
              <UiStatePanel
                state="error"
                title="Operazione non riuscita"
                message={actionError}
                testId="matchday-action-error"
              />
            ) : null}
          </TabPanel>
          </Tabs>
        </>
      ) : null}
    </PageContainer>
  );
}
