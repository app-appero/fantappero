import type { FantasyRole, LeagueListoneEntry } from "@fantappero/contracts";
import {
  AuctionBidPanel,
  Badge,
  Breadcrumb,
  Button,
  Card,
  CardBody,
  CardHeader,
  PageContainer,
  Tab,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeaderCell,
  TableRow,
  TabList,
  TabPanel,
  Tabs,
  UiStatePanel,
  WireframeSection,
} from "@fantappero/ui";
import { useCallback, useEffect, useMemo, useState } from "react";
import { fetchLeagueListone, refreshLeagueListone } from "../api/leagues";
import { getApiErrorMessage, useAuth } from "../auth/AuthContext";
import { loadStoredSession } from "../auth/sessionStorage";
import { useLocation } from "../router/simpleRouter";
import { parseWireframeStateFromSearch } from "../wireframes/useWireframeState";

type RoleTab = "all" | FantasyRole;

const ROLE_TABS: Array<{ value: RoleTab; label: string }> = [
  { value: "all", label: "Tutti" },
  { value: "P", label: "Portieri" },
  { value: "D", label: "Difensori" },
  { value: "C", label: "Centrocampisti" },
  { value: "A", label: "Attaccanti" },
];

const ROLE_LABEL: Record<FantasyRole, string> = {
  P: "Portiere",
  D: "Difensore",
  C: "Centrocampista",
  A: "Attaccante",
};

const DEMO_LISTONE: LeagueListoneEntry[] = [
  {
    athleteId: "demo-p-1",
    canonicalName: "Rui Patrício",
    seasonYear: 2026,
    officialRole: "P",
    effectiveRole: "P",
    providerPositionRaw: "Goalkeeper",
    mappingVersion: "v1.0.0",
    clubId: "demo-club-1",
    clubName: "Wolves",
    override: null,
  },
  {
    athleteId: "demo-d-1",
    canonicalName: "C. Coady",
    seasonYear: 2026,
    officialRole: "D",
    effectiveRole: "D",
    providerPositionRaw: "Defender",
    mappingVersion: "v1.0.0",
    clubId: "demo-club-1",
    clubName: "Wolves",
    override: null,
  },
  {
    athleteId: "demo-c-1",
    canonicalName: "Rúben Neves",
    seasonYear: 2026,
    officialRole: "C",
    effectiveRole: "A",
    providerPositionRaw: "Midfielder",
    mappingVersion: "v1.0.0",
    clubId: "demo-club-1",
    clubName: "Wolves",
    override: {
      role: "A",
      effectiveFromRound: null,
      pending: false,
      reason: "Override pre-asta",
    },
  },
  {
    athleteId: "demo-a-1",
    canonicalName: "R. Jiménez",
    seasonYear: 2026,
    officialRole: "A",
    effectiveRole: "A",
    providerPositionRaw: "Attacker",
    mappingVersion: "v1.0.0",
    clubId: "demo-club-1",
    clubName: "Wolves",
    override: null,
  },
];

function filterByTab(entries: LeagueListoneEntry[], tab: RoleTab): LeagueListoneEntry[] {
  if (tab === "all") {
    return entries;
  }
  return entries.filter((entry) => entry.effectiveRole === tab);
}

function initialDemoEntries(
  isDemoMode: boolean,
  demoState: ReturnType<typeof parseWireframeStateFromSearch> | null,
): LeagueListoneEntry[] {
  if (!isDemoMode) {
    return [];
  }
  if (
    demoState === "empty" ||
    demoState === "error" ||
    demoState === "loading" ||
    demoState === "forbidden"
  ) {
    return [];
  }
  return DEMO_LISTONE;
}

/** Schermata Asta: visuali sessione/offerta + listone ufficiale sotto. */
export function AuctionPage() {
  const { isDemoMode, activeLeagueId, activeLeague, can } = useAuth();
  const { search } = useLocation();
  const demoState = isDemoMode ? parseWireframeStateFromSearch(search) : null;
  const canManageSession = can(["market:manage"]);
  const isListoneAdmin = can(["league:admin"]);

  const [entries, setEntries] = useState<LeagueListoneEntry[]>(() =>
    initialDemoEntries(isDemoMode, demoState),
  );
  const [activeTab, setActiveTab] = useState<RoleTab>("all");
  const [loading, setLoading] = useState(() =>
    isDemoMode ? demoState === "loading" : true,
  );
  const [loadError, setLoadError] = useState<string | null>(() =>
    isDemoMode && demoState === "error"
      ? "Impossibile caricare il listone (demo)."
      : null,
  );
  const [refreshing, setRefreshing] = useState(false);
  const [refreshMessage, setRefreshMessage] = useState<string | null>(null);
  const [refreshError, setRefreshError] = useState<string | null>(null);

  const loadListone = useCallback(async () => {
    setRefreshMessage(null);
    setRefreshError(null);

    if (isDemoMode) {
      if (demoState === "loading") {
        setLoading(true);
        setEntries([]);
        setLoadError(null);
        return;
      }
      if (demoState === "error") {
        setLoading(false);
        setEntries([]);
        setLoadError("Impossibile caricare il listone (demo).");
        return;
      }
      if (demoState === "empty") {
        setLoading(false);
        setEntries([]);
        setLoadError(null);
        return;
      }
      if (demoState === "forbidden") {
        setLoading(false);
        setEntries([]);
        setLoadError(null);
        return;
      }
      setEntries(DEMO_LISTONE);
      setLoading(false);
      setLoadError(null);
      return;
    }

    if (!activeLeagueId) {
      setLoading(false);
      setEntries([]);
      setLoadError(null);
      return;
    }

    const stored = loadStoredSession();
    if (!stored?.accessToken) {
      setLoading(false);
      setEntries([]);
      setLoadError("Sessione non disponibile. Accedi di nuovo.");
      return;
    }

    setLoading(true);
    setLoadError(null);
    try {
      const rows = await fetchLeagueListone(stored.accessToken, activeLeagueId);
      setEntries(rows);
    } catch (error) {
      setEntries([]);
      setLoadError(getApiErrorMessage(error, "Impossibile caricare il listone."));
    } finally {
      setLoading(false);
    }
  }, [activeLeagueId, demoState, isDemoMode]);

  useEffect(() => {
    void loadListone();
  }, [loadListone]);

  const visibleEntries = useMemo(
    () => filterByTab(entries, activeTab),
    [activeTab, entries],
  );

  const onRefresh = async () => {
    setRefreshMessage(null);
    setRefreshError(null);

    if (isDemoMode) {
      setRefreshing(true);
      window.setTimeout(() => {
        setEntries(DEMO_LISTONE);
        setRefreshMessage("Listone aggiornato (demo).");
        setRefreshing(false);
      }, 400);
      return;
    }

    if (!activeLeagueId) {
      setRefreshError("Seleziona una lega per aggiornare il listone.");
      return;
    }
    const stored = loadStoredSession();
    if (!stored?.accessToken) {
      setRefreshError("Sessione non disponibile. Accedi di nuovo.");
      return;
    }

    setRefreshing(true);
    try {
      const result = await refreshLeagueListone(stored.accessToken, activeLeagueId);
      setRefreshMessage(
        `${result.message} Creati ${result.counters.listoneCreated}, aggiornati ${result.counters.listoneUpdated}, invariati ${result.counters.listoneUnchanged}.`,
      );
      const rows = await fetchLeagueListone(stored.accessToken, activeLeagueId);
      setEntries(rows);
      setLoadError(null);
    } catch (error) {
      setRefreshError(
        getApiErrorMessage(
          error,
          "Aggiornamento listone non riuscito. Verifica la chiave API-Football sul server.",
        ),
      );
    } finally {
      setRefreshing(false);
    }
  };

  if (isDemoMode && demoState === "forbidden") {
    return (
      <PageContainer
        title="Asta"
        header={
          <Breadcrumb items={[{ label: "Leghe", href: "/leghe" }, { label: "Asta" }]} />
        }
      >
        <UiStatePanel
          state="forbidden"
          title="Permessi insufficienti"
          message="Non puoi partecipare all'asta di questa lega."
          testId="auction-forbidden"
        />
      </PageContainer>
    );
  }

  return (
    <PageContainer
      title="Asta"
      header={
        <Breadcrumb items={[{ label: "Leghe", href: "/leghe" }, { label: "Asta" }]} />
      }
    >
      <div className="fa-auction-page">
        {canManageSession ? (
          <WireframeSection
            label="Gestione sessione (admin)"
            testId="wireframe-region-auction-admin"
          >
            <div className="fa-ds-showcase__row">
              <Button variant="primary">Apri asta</Button>
              <Button variant="secondary">Chiudi asta</Button>
            </div>
            <p>Sessione: Aperta · Partecipanti: 6/8</p>
          </WireframeSection>
        ) : null}

        <WireframeSection
          label="Offerta busta chiusa"
          testId="wireframe-region-auction-bid"
        >
          <AuctionBidPanel
            title="Nuova offerta"
            budgetLabel="Budget residuo"
            budgetValue="420 crediti"
            playerLabel="Giocatore"
            playerPlaceholder="Cerca giocatore…"
            bidLabel="Offerta (crediti)"
            bidPlaceholder="Es. 45"
            submitLabel="Invia offerta"
            statusLabel="Stato"
            statusMessage="Asta a buste chiuse — offerta visibile solo a te fino alla chiusura."
          />
        </WireframeSection>

        <Card data-testid="auction-listone-card">
          <CardHeader>
            <div className="fa-auction-listone__header">
              <div>
                <h2 className="fa-auction-listone__title">Listone ufficiale</h2>
                <p className="fa-auction-listone__subtitle">
                  {activeLeague
                    ? `Lega: ${activeLeague.name} · Stagione ${entries[0]?.seasonYear ?? "—"}`
                    : "Seleziona una lega dal selettore in alto."}
                </p>
              </div>
              {isListoneAdmin ? (
                <Button
                  variant="primary"
                  onClick={() => void onRefresh()}
                  disabled={refreshing || loading || (!isDemoMode && !activeLeagueId)}
                  data-testid="auction-listone-refresh"
                >
                  {refreshing ? "Aggiornamento…" : "Aggiorna"}
                </Button>
              ) : null}
            </div>
          </CardHeader>
          <CardBody>
            {refreshMessage ? (
              <UiStatePanel
                state="success"
                title="Listone aggiornato"
                message={refreshMessage}
                testId="auction-listone-refresh-success"
              />
            ) : null}
            {refreshError ? (
              <UiStatePanel
                state="error"
                title="Aggiornamento non riuscito"
                message={refreshError}
                testId="auction-listone-refresh-error"
              />
            ) : null}

            {loading ? (
              <UiStatePanel
                state="loading"
                title="Caricamento listone"
                message="Recupero calciatori e ruoli…"
                testId="auction-listone-loading"
              />
            ) : null}

            {!loading && loadError ? (
              <>
                <UiStatePanel
                  state="error"
                  title="Listone non disponibile"
                  message={loadError}
                  testId="auction-listone-error"
                />
                <Button variant="secondary" onClick={() => void loadListone()}>
                  Ricarica
                </Button>
              </>
            ) : null}

            {!loading && !loadError && !activeLeagueId && !isDemoMode ? (
              <UiStatePanel
                state="empty"
                title="Nessuna lega selezionata"
                message="Scegli una lega per consultare il listone."
                testId="auction-listone-no-league"
              />
            ) : null}

            {!loading && !loadError && (isDemoMode || activeLeagueId) ? (
              <Tabs
                value={activeTab}
                onValueChange={(value) => setActiveTab(value as RoleTab)}
                aria-label="Filtra listone per ruolo"
              >
                <TabList>
                  {ROLE_TABS.map((tab) => (
                    <Tab key={tab.value} value={tab.value}>
                      {tab.label}
                    </Tab>
                  ))}
                </TabList>
                {ROLE_TABS.map((tab) => (
                  <TabPanel key={tab.value} value={tab.value}>
                    {visibleEntries.length === 0 ? (
                      <UiStatePanel
                        state="empty"
                        title="Nessun calciatore"
                        message={
                          tab.value === "all"
                            ? "Il listone è vuoto. L'amministratore può aggiornarlo dal provider."
                            : `Nessun ${ROLE_LABEL[tab.value as FantasyRole].toLowerCase()} nel listone.`
                        }
                        testId={`auction-listone-empty-${tab.value}`}
                      />
                    ) : (
                      <Table compact data-testid={`auction-listone-table-${tab.value}`}>
                        <TableHead>
                          <TableRow>
                            <TableHeaderCell>Calciatore</TableHeaderCell>
                            <TableHeaderCell>Ruolo</TableHeaderCell>
                            <TableHeaderCell>Club</TableHeaderCell>
                            <TableHeaderCell>Posizione provider</TableHeaderCell>
                            <TableHeaderCell>Note</TableHeaderCell>
                          </TableRow>
                        </TableHead>
                        <TableBody>
                          {visibleEntries.map((entry) => (
                            <TableRow key={entry.athleteId}>
                              <TableCell>{entry.canonicalName}</TableCell>
                              <TableCell>
                                <Badge variant="accent">{entry.effectiveRole}</Badge>{" "}
                                {ROLE_LABEL[entry.effectiveRole]}
                              </TableCell>
                              <TableCell>{entry.clubName ?? "—"}</TableCell>
                              <TableCell>{entry.providerPositionRaw ?? "—"}</TableCell>
                              <TableCell>
                                {entry.override ? (
                                  <Badge variant="warning">
                                    {entry.override.pending
                                      ? `Override dal turno ${entry.override.effectiveFromRound ?? "?"}`
                                      : "Override attivo"}
                                  </Badge>
                                ) : (
                                  "—"
                                )}
                              </TableCell>
                            </TableRow>
                          ))}
                        </TableBody>
                      </Table>
                    )}
                  </TabPanel>
                ))}
              </Tabs>
            ) : null}
          </CardBody>
        </Card>
      </div>
    </PageContainer>
  );
}
