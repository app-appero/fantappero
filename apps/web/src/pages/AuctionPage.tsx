import type {
  FantasyRole,
  LeagueListoneEntry,
  MarketBidStatus,
  MarketSessionStatus,
} from "@fantappero/contracts";
import {
  AuctionBidPanel,
  Badge,
  Breadcrumb,
  Button,
  Card,
  CardBody,
  CardHeader,
  Input,
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
import { type FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import {
  closeAuctionSession,
  createAuctionSession,
  fetchAuctionSessions,
  fetchMyAuctionBids,
  resolveAuctionSession,
  submitAuctionBid,
  withdrawAuctionBid,
} from "../api/market";
import { fetchLeagueListone, fetchMyCredits } from "../api/leagues";
import { getApiErrorMessage, useAuth } from "../auth/AuthContext";
import { loadStoredSession } from "../auth/sessionStorage";
import { useMarketSessionFlow } from "../market/useMarketSessionFlow";
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

function roleBadgeVariant(role: FantasyRole): "success" | "warning" | "accent" | "danger" {
  if (role === "P") {
    return "success";
  }
  if (role === "D") {
    return "warning";
  }
  if (role === "C") {
    return "accent";
  }
  return "danger";
}

const ROLE_LABEL: Record<FantasyRole, string> = {
  P: "Portiere",
  D: "Difensore",
  C: "Centrocampista",
  A: "Attaccante",
};

const SESSION_STATUS_LABEL: Record<MarketSessionStatus, string> = {
  scheduled: "Programmata",
  open: "Aperta",
  closed: "Chiusa",
  resolved: "Risolta",
};

const SESSION_STATUS_VARIANT: Record<
  MarketSessionStatus,
  "success" | "warning" | "accent" | "danger" | "neutral"
> = {
  scheduled: "neutral",
  open: "success",
  closed: "warning",
  resolved: "accent",
};

const BID_STATUS_LABEL: Record<MarketBidStatus, string> = {
  submitted: "Inviata",
  expired: "Scaduta",
  won: "Vinta",
  lost: "Persa",
  cancelled: "Ritirata",
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

/** Schermata Asta: sessione a buste chiuse collegata alle API reali (EP08-01/02) + listone ufficiale. */
export function AuctionPage() {
  const { isDemoMode, activeLeagueId, activeLeague, can } = useAuth();
  const { search } = useLocation();
  const demoState = isDemoMode ? parseWireframeStateFromSearch(search) : null;
  const canManageSession = can(["market:manage"]);

  const [entries, setEntries] = useState<LeagueListoneEntry[]>(() =>
    initialDemoEntries(isDemoMode, demoState),
  );
  const [activeTab, setActiveTab] = useState<RoleTab>("all");
  const [loading, setLoading] = useState(() => (isDemoMode ? demoState === "loading" : true));
  const [loadError, setLoadError] = useState<string | null>(() =>
    isDemoMode && demoState === "error" ? "Impossibile caricare il listone (demo)." : null,
  );

  const [balance, setBalance] = useState<number | null>(isDemoMode ? 420 : null);

  const loadListone = useCallback(async () => {
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
      if (demoState === "empty" || demoState === "forbidden") {
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
      const [rows, credits] = await Promise.all([
        fetchLeagueListone(stored.accessToken, activeLeagueId),
        fetchMyCredits(stored.accessToken, activeLeagueId).catch(() => null),
      ]);
      setEntries(rows);
      if (credits) {
        setBalance(credits.balance);
      }
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

  const visibleEntries = useMemo(() => filterByTab(entries, activeTab), [activeTab, entries]);

  const flow = useMarketSessionFlow(
    {
      fetchSessions: fetchAuctionSessions,
      createSession: createAuctionSession,
      closeSession: closeAuctionSession,
      resolveSession: resolveAuctionSession,
      submitBid: submitAuctionBid,
      withdrawBid: withdrawAuctionBid,
      fetchMyBids: fetchMyAuctionBids,
    },
    { leagueId: activeLeagueId, active: !isDemoMode },
  );

  const [opensAt, setOpensAt] = useState("");
  const [closesAt, setClosesAt] = useState("");

  function handleCreateSession(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!opensAt || !closesAt) {
      return;
    }
    void flow.createSession({
      opensAt: new Date(opensAt).toISOString(),
      closesAt: new Date(closesAt).toISOString(),
    });
  }

  const [bidAthleteId, setBidAthleteId] = useState("");
  const [bidAmount, setBidAmount] = useState("");

  function handleSubmitBid(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const amount = Number(bidAmount);
    if (!bidAthleteId || !Number.isFinite(amount) || amount <= 0) {
      return;
    }
    void flow.submitBid(bidAthleteId, { amountCredits: amount }).then(() => {
      setBidAthleteId("");
      setBidAmount("");
    });
  }

  const playerOptions = useMemo(
    () => entries.map((entry) => ({ value: entry.athleteId, label: entry.canonicalName })),
    [entries],
  );

  const athleteNameById = useMemo(() => {
    const map = new Map<string, string>();
    for (const entry of entries) {
      map.set(entry.athleteId, entry.canonicalName);
    }
    return map;
  }, [entries]);

  if (isDemoMode && demoState === "forbidden") {
    return (
      <PageContainer
        title="Asta"
        header={<Breadcrumb items={[{ label: "Leghe", href: "/leghe" }, { label: "Asta" }]} />}
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
      header={<Breadcrumb items={[{ label: "Leghe", href: "/leghe" }, { label: "Asta" }]} />}
    >
      <div className="fa-auction-page">
        {canManageSession ? (
          <WireframeSection label="Gestione sessione (admin)" testId="wireframe-region-auction-admin">
            {isDemoMode ? (
              <div className="fa-ds-showcase__row">
                <Button variant="primary">Apri asta</Button>
                <Button variant="secondary">Chiudi asta</Button>
              </div>
            ) : null}
            {isDemoMode ? <p>Sessione: Aperta · Partecipanti: 6/8</p> : null}

            {!isDemoMode && flow.loading ? (
              <UiStatePanel
                state="loading"
                title="Caricamento sessioni"
                message="Recupero le sessioni d'asta…"
                testId="auction-admin-loading"
              />
            ) : null}

            {!isDemoMode && !flow.loading && flow.loadError ? (
              <UiStatePanel
                state="error"
                title="Sessioni non disponibili"
                message={flow.loadError}
                testId="auction-admin-error"
              />
            ) : null}

            {!isDemoMode && !flow.loading && !flow.loadError && flow.currentSession ? (
              <div data-testid="auction-admin-current-session">
                <p>
                  Sessione: <Badge variant={SESSION_STATUS_VARIANT[flow.currentSession.status]}>
                    {SESSION_STATUS_LABEL[flow.currentSession.status]}
                  </Badge>{" "}
                  · Offerte: {flow.currentSession.bidCount ?? "—"}
                </p>
                <div className="fa-ds-showcase__row">
                  <Button
                    variant="secondary"
                    disabled={flow.currentSession.status !== "open" || flow.sessionActionPending}
                    onClick={() => void flow.closeCurrentSession()}
                  >
                    Chiudi asta
                  </Button>
                  <Button
                    variant="primary"
                    disabled={flow.currentSession.status !== "closed" || flow.sessionActionPending}
                    onClick={() => void flow.resolveCurrentSession()}
                  >
                    Risolvi asta
                  </Button>
                </div>
              </div>
            ) : null}

            {!isDemoMode && !flow.loading && !flow.loadError && !flow.currentSession ? (
              <UiStatePanel
                state="empty"
                title="Nessuna sessione d'asta"
                message="Crea la finestra d'asta a buste chiuse per iniziare."
                testId="auction-admin-empty"
              />
            ) : null}

            {!isDemoMode && flow.sessionActionError ? (
              <UiStatePanel
                state="error"
                title="Operazione non riuscita"
                message={flow.sessionActionError}
                testId="auction-admin-action-error"
              />
            ) : null}

            {!isDemoMode && flow.resolution ? (
              <div data-testid="auction-resolution-outcomes">
                <h3>Esiti risoluzione</h3>
                {flow.resolution.outcomes.length === 0 ? (
                  <p>Nessuna offerta da assegnare.</p>
                ) : (
                  <ul>
                    {flow.resolution.outcomes.map((outcome) => (
                      <li key={outcome.athleteId}>
                        {outcome.athleteName}:{" "}
                        {outcome.outcome === "assigned"
                          ? `assegnato per ${outcome.amountCredits} crediti`
                          : outcome.outcome === "tiebreak"
                            ? "spareggio aperto (parità)"
                            : "non assegnato"}
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            ) : null}

            {!isDemoMode ? (
              <form
                data-testid="auction-create-session-form"
                onSubmit={handleCreateSession}
                className="fa-auction-page__create-session"
              >
                <Input
                  label="Apertura"
                  name="opens-at"
                  type="datetime-local"
                  value={opensAt}
                  onChange={(event) => setOpensAt(event.target.value)}
                  required
                />
                <Input
                  label="Chiusura"
                  name="closes-at"
                  type="datetime-local"
                  value={closesAt}
                  onChange={(event) => setClosesAt(event.target.value)}
                  required
                />
                {flow.createError ? (
                  <UiStatePanel
                    state="error"
                    title="Sessione non creata"
                    message={flow.createError}
                    testId="auction-create-session-error"
                  />
                ) : null}
                <Button type="submit" variant="primary" disabled={flow.creating}>
                  {flow.creating ? "Creazione…" : "Crea sessione"}
                </Button>
              </form>
            ) : null}
          </WireframeSection>
        ) : null}

        <WireframeSection label="Offerta busta chiusa" testId="wireframe-region-auction-bid">
          {!isDemoMode && flow.currentSession?.status !== "open" ? (
            <UiStatePanel
              state="empty"
              title="Asta non aperta"
              message="Le offerte si possono inviare solo mentre la sessione è aperta."
              testId="auction-bid-not-open"
            />
          ) : (
            <AuctionBidPanel
              title="Nuova offerta"
              budgetLabel="Budget residuo"
              budgetValue={balance !== null ? `${balance} crediti` : "—"}
              playerLabel="Giocatore"
              playerPlaceholder="Scegli un giocatore…"
              playerOptions={isDemoMode ? undefined : playerOptions}
              playerValue={isDemoMode ? undefined : bidAthleteId}
              onPlayerChange={isDemoMode ? undefined : (event) => setBidAthleteId(event.target.value)}
              bidLabel="Offerta (crediti)"
              bidPlaceholder="Es. 45"
              bidValue={isDemoMode ? undefined : bidAmount}
              onBidChange={isDemoMode ? undefined : (event) => setBidAmount(event.target.value)}
              onSubmit={isDemoMode ? undefined : handleSubmitBid}
              submitting={flow.bidSubmitting}
              disabled={isDemoMode || !flow.currentSession}
              submitLabel="Invia offerta"
              statusLabel="Stato"
              statusMessage="Asta a buste chiuse — offerta visibile solo a te fino alla chiusura."
              errorMessage={isDemoMode ? undefined : (flow.bidError ?? undefined)}
            />
          )}

          {flow.bidSuccess ? (
            <UiStatePanel
              state="success"
              title="Fatto"
              message={flow.bidSuccess}
              testId="auction-bid-success"
            />
          ) : null}

          {!isDemoMode && flow.myBids.length > 0 ? (
            <Table compact data-testid="auction-my-bids-table">
              <TableHead>
                <TableRow>
                  <TableHeaderCell>Giocatore</TableHeaderCell>
                  <TableHeaderCell>Offerta</TableHeaderCell>
                  <TableHeaderCell>Stato</TableHeaderCell>
                  <TableHeaderCell>Azioni</TableHeaderCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {flow.myBids.map((bid) => (
                  <TableRow key={bid.id}>
                    <TableCell>{athleteNameById.get(bid.athleteId) ?? bid.athleteName}</TableCell>
                    <TableCell>{bid.amountCredits} crediti</TableCell>
                    <TableCell>
                      <Badge variant={bid.status === "submitted" ? "success" : "neutral"}>
                        {BID_STATUS_LABEL[bid.status]}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      {bid.status === "submitted" ? (
                        <Button
                          variant="secondary"
                          size="sm"
                          onClick={() => void flow.withdrawBid(bid.athleteId)}
                        >
                          Ritira
                        </Button>
                      ) : (
                        "—"
                      )}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          ) : null}
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
            </div>
          </CardHeader>
          <CardBody>
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
                            ? "Il listone è vuoto. Verrà popolato dagli operatori della piattaforma."
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
                                <Badge variant={roleBadgeVariant(entry.effectiveRole)}>
                                  {entry.effectiveRole}
                                </Badge>{" "}
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
