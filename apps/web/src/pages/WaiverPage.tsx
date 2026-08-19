import type { LeagueListoneEntry, MarketBidStatus, MarketSessionStatus } from "@fantappero/contracts";
import {
  AuctionBidPanel,
  Badge,
  Breadcrumb,
  Button,
  Input,
  PageContainer,
  Select,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeaderCell,
  TableRow,
  UiStatePanel,
  WireframeSection,
} from "@fantappero/ui";
import { type FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import {
  closeWaiverSession,
  createWaiverSession,
  fetchMyWaiverBids,
  fetchWaiverSessions,
  resolveWaiverSession,
  submitWaiverBid,
  withdrawWaiverBid,
} from "../api/market";
import { fetchLeagueListone, fetchMyCredits, fetchMyFantasyTeam } from "../api/leagues";
import { getApiErrorMessage, useAuth } from "../auth/AuthContext";
import { loadStoredSession } from "../auth/sessionStorage";
import { useMarketSessionFlow } from "../market/useMarketSessionFlow";
import { useLocation } from "../router/simpleRouter";
import { parseWireframeStateFromSearch } from "../wireframes/useWireframeState";

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

/** Schermata Svincolati: mercato waiver a buste chiuse con giocatore da tagliare (EP08-03 / FR-MKT-01). */
export function WaiverPage() {
  const { isDemoMode, activeLeagueId, can } = useAuth();
  const { search } = useLocation();
  const demoState = isDemoMode ? parseWireframeStateFromSearch(search) : null;
  const canManageSession = can(["market:manage"]);

  const [entries, setEntries] = useState<LeagueListoneEntry[]>([]);
  const [balance, setBalance] = useState<number | null>(isDemoMode ? 380 : null);
  const [rosterOptions, setRosterOptions] = useState<Array<{ value: string; label: string }>>([]);
  const [loading, setLoading] = useState(() => (isDemoMode ? demoState === "loading" : true));
  const [loadError, setLoadError] = useState<string | null>(() =>
    isDemoMode && demoState === "error" ? "Impossibile caricare i dati (demo)." : null,
  );

  const loadData = useCallback(async () => {
    if (isDemoMode) {
      setLoading(demoState === "loading");
      setLoadError(demoState === "error" ? "Impossibile caricare i dati (demo)." : null);
      return;
    }
    if (!activeLeagueId) {
      setLoading(false);
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
      const [listoneRows, credits, myTeam] = await Promise.all([
        fetchLeagueListone(stored.accessToken, activeLeagueId),
        fetchMyCredits(stored.accessToken, activeLeagueId).catch(() => null),
        fetchMyFantasyTeam(stored.accessToken, activeLeagueId).catch(() => null),
      ]);
      setEntries(listoneRows);
      if (credits) {
        setBalance(credits.balance);
      }
      if (myTeam) {
        setRosterOptions(
          myTeam.slots
            .filter((slot) => slot.athleteId !== null)
            .map((slot) => ({
              value: slot.athleteId as string,
              label: slot.athleteName ?? "Giocatore",
            })),
        );
      }
    } catch (error) {
      setLoadError(getApiErrorMessage(error, "Impossibile caricare i dati del mercato svincolati."));
    } finally {
      setLoading(false);
    }
  }, [activeLeagueId, demoState, isDemoMode]);

  useEffect(() => {
    void loadData();
  }, [loadData]);

  const flow = useMarketSessionFlow(
    {
      fetchSessions: fetchWaiverSessions,
      createSession: createWaiverSession,
      closeSession: closeWaiverSession,
      resolveSession: resolveWaiverSession,
      submitBid: submitWaiverBid,
      withdrawBid: withdrawWaiverBid,
      fetchMyBids: fetchMyWaiverBids,
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
  const [releaseAthleteId, setReleaseAthleteId] = useState("");

  function handleSubmitBid(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const amount = Number(bidAmount);
    if (!bidAthleteId || !releaseAthleteId || !Number.isFinite(amount) || amount <= 0) {
      return;
    }
    void flow
      .submitBid(bidAthleteId, { amountCredits: amount, releaseAthleteId })
      .then(() => {
        setBidAthleteId("");
        setBidAmount("");
        setReleaseAthleteId("");
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
        title="Svincolati"
        header={<Breadcrumb items={[{ label: "Leghe", href: "/leghe" }, { label: "Svincolati" }]} />}
      >
        <UiStatePanel
          state="forbidden"
          title="Permessi insufficienti"
          message="Non puoi partecipare al mercato svincolati di questa lega."
          testId="waiver-forbidden"
        />
      </PageContainer>
    );
  }

  return (
    <PageContainer
      title="Svincolati"
      header={<Breadcrumb items={[{ label: "Leghe", href: "/leghe" }, { label: "Svincolati" }]} />}
    >
      <div className="fa-auction-page">
        {loading ? (
          <UiStatePanel
            state="loading"
            title="Caricamento"
            message="Recupero i dati del mercato svincolati…"
            testId="waiver-loading"
          />
        ) : null}

        {!loading && loadError ? (
          <UiStatePanel
            state="error"
            title="Dati non disponibili"
            message={loadError}
            testId="waiver-load-error"
          />
        ) : null}

        {!loading && !loadError && !isDemoMode && !activeLeagueId ? (
          <UiStatePanel
            state="empty"
            title="Nessuna lega selezionata"
            message="Scegli una lega per accedere al mercato svincolati."
            testId="waiver-no-league"
          />
        ) : null}

        {!loading && !loadError && (isDemoMode || activeLeagueId) ? (
          <>
            {canManageSession ? (
              <WireframeSection label="Gestione sessione svincolati (admin)" testId="wireframe-region-waiver-admin">
                {isDemoMode ? (
                  <div className="fa-ds-showcase__row">
                    <Button variant="primary">Apri svincolati</Button>
                    <Button variant="secondary">Chiudi svincolati</Button>
                  </div>
                ) : null}

                {!isDemoMode && flow.loading ? (
                  <UiStatePanel
                    state="loading"
                    title="Caricamento sessioni"
                    message="Recupero le sessioni svincolati…"
                    testId="waiver-admin-loading"
                  />
                ) : null}

                {!isDemoMode && !flow.loading && flow.loadError ? (
                  <UiStatePanel
                    state="error"
                    title="Sessioni non disponibili"
                    message={flow.loadError}
                    testId="waiver-admin-error"
                  />
                ) : null}

                {!isDemoMode && !flow.loading && !flow.loadError && flow.currentSession ? (
                  <div data-testid="waiver-admin-current-session">
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
                        Chiudi svincolati
                      </Button>
                      <Button
                        variant="primary"
                        disabled={flow.currentSession.status !== "closed" || flow.sessionActionPending}
                        onClick={() => void flow.resolveCurrentSession()}
                      >
                        Risolvi svincolati
                      </Button>
                    </div>
                  </div>
                ) : null}

                {!isDemoMode && !flow.loading && !flow.loadError && !flow.currentSession ? (
                  <UiStatePanel
                    state="empty"
                    title="Nessuna sessione svincolati"
                    message="Crea la finestra svincolati a buste chiuse per iniziare."
                    testId="waiver-admin-empty"
                  />
                ) : null}

                {!isDemoMode && flow.sessionActionError ? (
                  <UiStatePanel
                    state="error"
                    title="Operazione non riuscita"
                    message={flow.sessionActionError}
                    testId="waiver-admin-action-error"
                  />
                ) : null}

                {!isDemoMode && flow.resolution ? (
                  <div data-testid="waiver-resolution-outcomes">
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
                    data-testid="waiver-create-session-form"
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
                        testId="waiver-create-session-error"
                      />
                    ) : null}
                    <Button type="submit" variant="primary" disabled={flow.creating}>
                      {flow.creating ? "Creazione…" : "Crea sessione"}
                    </Button>
                  </form>
                ) : null}
              </WireframeSection>
            ) : null}

            <WireframeSection label="Offerta svincolati" testId="wireframe-region-waiver-bid">
              {!isDemoMode && flow.currentSession?.status !== "open" ? (
                <UiStatePanel
                  state="empty"
                  title="Svincolati non aperti"
                  message="Le offerte si possono inviare solo mentre la sessione è aperta."
                  testId="waiver-bid-not-open"
                />
              ) : (
                <AuctionBidPanel
                  testId="waiver-bid-panel"
                  title="Nuova offerta svincolati"
                  budgetLabel="Budget residuo"
                  budgetValue={balance !== null ? `${balance} crediti` : "—"}
                  playerLabel="Giocatore da acquisire"
                  playerPlaceholder="Scegli un giocatore…"
                  playerOptions={isDemoMode ? undefined : playerOptions}
                  playerValue={isDemoMode ? undefined : bidAthleteId}
                  onPlayerChange={isDemoMode ? undefined : (event) => setBidAthleteId(event.target.value)}
                  bidLabel="Offerta (crediti)"
                  bidPlaceholder="Es. 20"
                  bidValue={isDemoMode ? undefined : bidAmount}
                  onBidChange={isDemoMode ? undefined : (event) => setBidAmount(event.target.value)}
                  onSubmit={isDemoMode ? undefined : handleSubmitBid}
                  submitting={flow.bidSubmitting}
                  disabled={isDemoMode || !flow.currentSession}
                  submitLabel="Invia offerta"
                  statusLabel="Stato"
                  statusMessage="Offerta valida solo se abbinata a un giocatore da svincolare."
                  errorMessage={isDemoMode ? undefined : (flow.bidError ?? undefined)}
                  extraField={
                    isDemoMode ? undefined : (
                      <Select
                        label="Giocatore da svincolare"
                        name="waiver-release-athlete"
                        options={rosterOptions}
                        placeholder="Scegli chi tagliare…"
                        value={releaseAthleteId}
                        onChange={(event) => setReleaseAthleteId(event.target.value)}
                        disabled={isDemoMode || !flow.currentSession}
                      />
                    )
                  }
                />
              )}

              {flow.bidSuccess ? (
                <UiStatePanel
                  state="success"
                  title="Fatto"
                  message={flow.bidSuccess}
                  testId="waiver-bid-success"
                />
              ) : null}

              {!isDemoMode && flow.myBids.length > 0 ? (
                <Table compact data-testid="waiver-my-bids-table">
                  <TableHead>
                    <TableRow>
                      <TableHeaderCell>Giocatore</TableHeaderCell>
                      <TableHeaderCell>Svincola</TableHeaderCell>
                      <TableHeaderCell>Offerta</TableHeaderCell>
                      <TableHeaderCell>Stato</TableHeaderCell>
                      <TableHeaderCell>Azioni</TableHeaderCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {flow.myBids.map((bid) => (
                      <TableRow key={bid.id}>
                        <TableCell>{athleteNameById.get(bid.athleteId) ?? bid.athleteName}</TableCell>
                        <TableCell>{bid.releaseAthleteName ?? "—"}</TableCell>
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
          </>
        ) : null}
      </div>
    </PageContainer>
  );
}
