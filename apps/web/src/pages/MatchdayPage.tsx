import type {
  FantasyTurnDetail,
  FantasyTurnPreview,
  FantasyTurnSummary,
  FantasyTurnKind,
} from "@fantappero/contracts";
import { mapFixtureMatchStatus } from "@fantappero/contracts";
import {
  Badge,
  Breadcrumb,
  Button,
  Card,
  CardBody,
  CardHeader,
  MatchCard,
  PageContainer,
  Tab,
  TabList,
  TabPanel,
  Tabs,
  UiStatePanel,
} from "@fantappero/ui";
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  excludeFantasyTurnFixture,
  ensureFantasyTurns,
  fetchFantasyTurn,
  fetchFantasyTurns,
  generateFantasyTurn,
  openFantasyTurn,
  previewFantasyTurn,
  recalculateFantasyTurnCutoff,
} from "../api/leagues";
import { getApiErrorMessage, useAuth } from "../auth/AuthContext";
import { loadStoredSession } from "../auth/sessionStorage";
import { useLiveTurnPolling } from "../matchday/useLiveTurnPolling";
import { useLocation } from "../router/simpleRouter";
import { parseWireframeStateFromSearch } from "../wireframes/useWireframeState";

const STATUS_LABEL: Record<string, string> = {
  scheduled: "Programmato",
  open: "Aperto",
  locked: "Chiuso",
  skipped: "Non disputato",
};

const MATCH_STATUS_LABEL: Record<string, string> = {
  scheduled: "In programma",
  live: "In corso",
  finished: "Terminata",
  postponed: "Rinviata",
};

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
      competitionName: "Premier League",
      providerId: 1035055,
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
      competitionName: "Serie A",
      providerId: 1035056,
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

/** Turni europei — consultazione e sync automatico (EP06-01). */
export function MatchdayPage() {
  const { isDemoMode, activeLeagueId, can } = useAuth();
  const { search } = useLocation();
  const demoState = isDemoMode ? parseWireframeStateFromSearch(search) : null;
  const params = new URLSearchParams(search.startsWith("?") ? search.slice(1) : search);
  const initialTab = params.get("tab") === "risultati" ? "risultati" : "turno";
  const [tab, setTab] = useState(initialTab);

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
  const [preview, setPreview] = useState<FantasyTurnPreview | null>(null);
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
  const [anchorDate, setAnchorDate] = useState("2026-08-15");
  const [kind, setKind] = useState<FantasyTurnKind>("weekend");

  const isAdmin = can(["league:admin"]);
  const canView = can(["matchday:view"]);

  const showForbidden = useMemo(() => {
    if (isDemoMode && demoState === "forbidden") {
      return true;
    }
    return !canView;
  }, [canView, demoState, isDemoMode]);

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
      if (list.length === 0) {
        setSelected(null);
      } else {
        const first = list[0];
        if (!first) {
          setSelected(null);
        } else {
          const detail = await fetchFantasyTurn(session.accessToken, activeLeagueId, first.id);
          setSelected(detail);
        }
      }
    } catch (error) {
      setLoadError(getApiErrorMessage(error, "Impossibile caricare i turni."));
      setTurns([]);
      setSelected(null);
    } finally {
      setLoading(false);
    }
  }, [activeLeagueId, demoState, isDemoMode]);

  useEffect(() => {
    void loadTurns();
  }, [loadTurns]);

  const { degraded: liveUpdateDegraded } = useLiveTurnPolling(
    activeLeagueId,
    selected,
    setSelected,
    !isDemoMode,
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

  async function runPreview() {
    if (isDemoMode) {
      setPreview({
        kind,
        windowStartAt: DEMO_TURN.windowStartAt,
        windowEndAt: DEMO_TURN.windowEndAt,
        timezone: "Europe/Rome",
        eligibleCount: DEMO_TURN.fixtureCount,
        minRequired: 10,
        thresholdOk: true,
        skipReason: null,
        cutoffAt: DEMO_TURN.cutoffAt,
        fixtures: DEMO_TURN.fixtures,
      });
      setActionMessage("Anteprima demo pronta.");
      return;
    }
    const session = loadStoredSession();
    if (!session?.accessToken || !activeLeagueId) {
      return;
    }
    setBusy(true);
    setActionError(null);
    setActionMessage(null);
    try {
      const result = await previewFantasyTurn(session.accessToken, activeLeagueId, {
        kind,
        anchorDate,
      });
      setPreview(result);
      setActionMessage(
        result.thresholdOk
          ? `Anteprima: ${result.eligibleCount} partite eleggibili.`
          : (result.skipReason ?? "Soglia non raggiunta."),
      );
    } catch (error) {
      setActionError(getApiErrorMessage(error, "Anteprima non disponibile."));
    } finally {
      setBusy(false);
    }
  }

  async function runEnsure() {
    if (isDemoMode) {
      setActionMessage("Turni sincronizzati dal calendario (demo).");
      setSelected(DEMO_TURN);
      setTurns([DEMO_TURN]);
      return;
    }
    const session = loadStoredSession();
    if (!session?.accessToken || !activeLeagueId) {
      return;
    }
    setBusy(true);
    setActionError(null);
    setActionMessage(null);
    try {
      const result = await ensureFantasyTurns(session.accessToken, activeLeagueId);
      setActionMessage(
        `Sincronizzazione completata: ${result.created} creati, ${result.opened} aperti, ` +
          `${result.upgraded} aggiornati, ${result.waiting} in attesa di partite.`,
      );
      await loadTurns();
    } catch (error) {
      setActionError(getApiErrorMessage(error, "Sincronizzazione turni non riuscita."));
    } finally {
      setBusy(false);
    }
  }

  async function runGenerate() {
    if (isDemoMode) {
      setActionMessage("Turno generato (demo).");
      setSelected(DEMO_TURN);
      setTurns([DEMO_TURN]);
      return;
    }
    const session = loadStoredSession();
    if (!session?.accessToken || !activeLeagueId) {
      return;
    }
    setBusy(true);
    setActionError(null);
    setActionMessage(null);
    try {
      const detail = await generateFantasyTurn(session.accessToken, activeLeagueId, {
        kind,
        anchorDate,
      });
      setSelected(detail);
      setActionMessage(
        detail.status === "skipped"
          ? (detail.skipReason ?? "Turno non disputato.")
          : `Turno ${detail.number} generato.`,
      );
      await loadTurns();
      setSelected(detail);
    } catch (error) {
      setActionError(getApiErrorMessage(error, "Generazione turno non riuscita."));
    } finally {
      setBusy(false);
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

      {!showForbidden && loading ? (
        <UiStatePanel
          state="loading"
          title="Caricamento turni"
          message="Recupero del calendario europeo in corso…"
          testId="matchday-loading"
        />
      ) : null}

      {!showForbidden && !loading && loadError ? (
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

      {!showForbidden && !loading && !loadError && !activeLeagueId && !isDemoMode ? (
        <UiStatePanel
          state="empty"
          title="Nessuna lega attiva"
          message="Seleziona una lega per consultare i turni europei."
          testId="matchday-no-league"
        />
      ) : null}

      {!showForbidden && !loading && !loadError && (activeLeagueId || isDemoMode) ? (
        <Tabs value={tab} onValueChange={setTab}>
          <TabList aria-label="Sezioni turno">
            <Tab value="turno">Turno</Tab>
            <Tab value="risultati">Risultati</Tab>
          </TabList>
          <TabPanel value="turno">
            {turns.length === 0 ? (
              <UiStatePanel
                state="empty"
                title="Nessun turno ancora"
                message="I turni vengono calcolati automaticamente dal sistema in base ai campionati della lega. Se non ne vedi ancora, attendi il sync del calendario o usa «Aggiorna dal calendario»."
                testId="matchday-empty"
              />
            ) : (
              <div className="fa-ds-showcase__stack" data-testid="matchday-turn-list">
                <Card>
                  <CardHeader title="Turni della lega" />
                  <CardBody>
                    <ul className="fa-ds-list">
                      {turns.map((turn) => (
                        <li key={turn.id}>
                          <Button
                            type="button"
                            variant={selected?.id === turn.id ? "primary" : "ghost"}
                            onClick={() => void selectTurn(turn.id)}
                            data-testid={`matchday-turn-${turn.number}`}
                          >
                            Turno {turn.number} — {STATUS_LABEL[turn.effectiveStatus] ?? turn.effectiveStatus}
                          </Button>
                        </li>
                      ))}
                    </ul>
                  </CardBody>
                </Card>
              </div>
            )}

            {selected ? (
              <Card data-testid="matchday-turn-detail">
                <CardHeader title={`Turno ${selected.number}`} />
                <CardBody>
                  <p>
                    Stato: <strong>{STATUS_LABEL[selected.effectiveStatus] ?? selected.effectiveStatus}</strong>
                    {selected.status !== selected.effectiveStatus
                      ? ` (persistito: ${STATUS_LABEL[selected.status]})`
                      : null}
                  </p>
                  <p>
                    Punteggi:{" "}
                    <Badge
                      variant={selected.homologationStatus === "homologated" ? "success" : "warning"}
                      data-testid="matchday-homologation-status"
                    >
                      {selected.homologationStatus === "homologated" ? "Finale" : "Provvisorio"}
                    </Badge>
                    {liveUpdateDegraded ? (
                      <span
                        data-testid="matchday-live-degraded"
                        style={{
                          marginLeft: "var(--fa-space-sm)",
                          color: "var(--fa-color-foreground-muted)",
                        }}
                      >
                        Aggiornamento live rallentato, nuovo tentativo in corso…
                      </span>
                    ) : null}
                  </p>
                  <p>Finestra: {formatDateTime(selected.windowStartAt)} → {formatDateTime(selected.windowEndAt)}</p>
                  <p>Cutoff formazione: {formatDateTime(selected.cutoffAt)}</p>
                  {selected.fixtures.some((fixture) => fixture.lockLatchedAt) ? (
                    <p data-testid="matchday-cutoff-latch">
                      Un rinvio o un cambio orario non sblocca le partite il cui kickoff originale è
                      già trascorso. Le mosse tattiche già usate restano consumate.
                    </p>
                  ) : null}
                  {selected.skipReason ? <p>{selected.skipReason}</p> : null}
                  <div className="fa-ds-showcase__row">
                    {isAdmin && selected.status === "scheduled" ? (
                      <Button type="button" disabled={busy} onClick={() => void runOpen()} data-testid="matchday-open">
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
                  <div className="fa-ds-showcase__stack" data-testid="matchday-fixtures">
                    {selected.fixtures.map((fixture) => (
                      <div key={fixture.id} className="fa-ds-showcase__row">
                        <MatchCard
                          homeTeam={fixture.homeClubName}
                          awayTeam={fixture.awayClubName}
                          kickoffLabel={formatDateTime(fixture.kickoffAt)}
                          status={mapFixtureMatchStatus(fixture.statusShort)}
                          statusLabel={
                            MATCH_STATUS_LABEL[mapFixtureMatchStatus(fixture.statusShort)] ??
                            fixture.statusShort
                          }
                          contextLabel={fixture.competitionName ?? "Campionato"}
                          score={
                            fixture.homeGoals !== null && fixture.awayGoals !== null
                              ? { home: fixture.homeGoals, away: fixture.awayGoals }
                              : null
                          }
                        />
                        {fixture.lockLatchedAt ? (
                          <p data-testid={`matchday-lock-latched-${fixture.fixtureId}`}>
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
                </CardBody>
              </Card>
            ) : null}

            {isAdmin ? (
              <Card data-testid="matchday-admin">
                <CardHeader title="Calendario turni" />
                <CardBody>
                  <p>
                    Il sistema raggruppa automaticamente le partite dei campionati scelti in turni
                    weekend e infrasettimanali. Usa il pulsante per forzare un aggiornamento.
                  </p>
                  <div className="fa-ds-showcase__row">
                    <Button
                      type="button"
                      disabled={busy}
                      onClick={() => void runEnsure()}
                      data-testid="matchday-ensure"
                    >
                      Aggiorna dal calendario
                    </Button>
                  </div>
                  <details>
                    <summary>Manuale avanzato</summary>
                    <label>
                      Tipo
                      <select
                        value={kind}
                        onChange={(event) => setKind(event.target.value as FantasyTurnKind)}
                        data-testid="matchday-kind"
                      >
                        <option value="weekend">Weekend (ven–lun)</option>
                        <option value="midweek">Infrasettimanale (mar–gio)</option>
                      </select>
                    </label>
                    <label>
                      Data di riferimento
                      <input
                        type="date"
                        value={anchorDate}
                        onChange={(event) => setAnchorDate(event.target.value)}
                        data-testid="matchday-anchor"
                      />
                    </label>
                    <div className="fa-ds-showcase__row">
                      <Button
                        type="button"
                        variant="secondary"
                        disabled={busy}
                        onClick={() => void runPreview()}
                        data-testid="matchday-preview"
                      >
                        Anteprima
                      </Button>
                      <Button
                        type="button"
                        variant="secondary"
                        disabled={busy}
                        onClick={() => void runGenerate()}
                        data-testid="matchday-generate"
                      >
                        Genera turno
                      </Button>
                    </div>
                    {preview ? (
                      <p data-testid="matchday-preview-result">
                        {preview.eligibleCount}/{preview.minRequired} partite — cutoff{" "}
                        {formatDateTime(preview.cutoffAt)}
                      </p>
                    ) : null}
                  </details>
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
          <TabPanel value="risultati">
            <UiStatePanel
              state="empty"
              title="Risultati non ancora disponibili"
              message="Il tab risultati arriverà con le fasi di scoring successive."
              testId="matchday-results-soon"
            />
          </TabPanel>
        </Tabs>
      ) : null}
    </PageContainer>
  );
}
