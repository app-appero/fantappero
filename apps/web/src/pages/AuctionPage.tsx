import type {
  LeagueListoneEntry,
  MarketBidStatus,
  MarketSessionStatus,
  RosterOccupancyEntry,
} from "@fantappero/contracts";
import {
  AuctionBidPanel,
  Badge,
  Button,
  Input,
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
import { AthleteName } from "../athletes/AthleteCard";
import { RosterColLabel } from "./roster/RosterActionButton";
import {
  closeAuctionSession,
  createAuctionSession,
  fetchAuctionSessions,
  fetchMyAuctionBids,
  resolveAuctionSession,
  submitAuctionBid,
  withdrawAuctionBid,
} from "../api/market";
import { fetchLeagueListone, fetchMyCredits, fetchRosterOccupancy } from "../api/leagues";
import { AthleteChooser } from "../components/AthleteChooser";
import { getApiErrorMessage, useAuth } from "../auth/AuthContext";
import { loadStoredSession } from "../auth/sessionStorage";
import { useMarketGate } from "../market/MarketGateContext";
import { useMarketSessionFlow } from "../market/useMarketSessionFlow";
import { useLocation } from "../router/simpleRouter";
import { parseWireframeStateFromSearch } from "../wireframes/useWireframeState";

const SESSION_STATUS_LABEL: Record<MarketSessionStatus, string> = {
  scheduled: "Programmata",
  open: "Aperta",
  closed: "Chiusa",
  resolved: "Risolta",
};

function formatSessionDate(iso: string): string {
  return new Date(iso).toLocaleString("it-IT", { dateStyle: "medium", timeStyle: "short" });
}

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
    photoUrl: null,
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
    photoUrl: null,
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
    photoUrl: null,
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
    photoUrl: null,
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

/** Schermata Asta: sessione a buste chiuse collegata alle API reali (EP08-01/02); i calciatori si scelgono dal selettore in «Nuova offerta». */
export function AuctionPage() {
  const { isDemoMode, activeLeagueId, can } = useAuth();
  const { search } = useLocation();
  const demoState = isDemoMode ? parseWireframeStateFromSearch(search) : null;
  const canManageSession = can(["market:manage"]);
  const { marketOpen } = useMarketGate();

  const [entries, setEntries] = useState<LeagueListoneEntry[]>(() =>
    initialDemoEntries(isDemoMode, demoState),
  );
  const [occupancy, setOccupancy] = useState<RosterOccupancyEntry[]>([]);
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
      const [rows, credits, owned] = await Promise.all([
        fetchLeagueListone(stored.accessToken, activeLeagueId),
        fetchMyCredits(stored.accessToken, activeLeagueId).catch(() => null),
        fetchRosterOccupancy(stored.accessToken, activeLeagueId).catch(() => []),
      ]);
      setEntries(rows);
      setOccupancy(owned);
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

  const ownedAthleteIds = useMemo(
    () => new Set(occupancy.map((row) => row.athleteId)),
    [occupancy],
  );

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

  const athleteNameById = useMemo(() => {
    const map = new Map<string, string>();
    for (const entry of entries) {
      map.set(entry.athleteId, entry.canonicalName);
    }
    return map;
  }, [entries]);

  if (isDemoMode && demoState === "forbidden") {
    return (
      <UiStatePanel
        state="forbidden"
        title="Permessi insufficienti"
        message="Non puoi partecipare all'asta di questa lega."
        testId="auction-forbidden"
      />
    );
  }

  return (
    <div className="fa-auction-page">
      {canManageSession ? (
          <WireframeSection label="Gestione sessione (admin)" testId="wireframe-region-auction-admin">
            {isDemoMode ? (
              <div className="fa-ds-showcase__row">
                <Button variant="primary" disabled={!marketOpen}>
                  Apri asta
                </Button>
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
                <p data-testid="auction-admin-window">
                  Apre {formatSessionDate(flow.currentSession.opensAt)} · chiude{" "}
                  {formatSessionDate(flow.currentSession.closesAt)}
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
                        <AthleteName athleteId={outcome.athleteId}>{outcome.athleteName}</AthleteName>:{" "}
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
                <Button type="submit" variant="primary" disabled={flow.creating || !marketOpen}>
                  {flow.creating ? "Creazione…" : "Crea sessione"}
                </Button>
              </form>
            ) : null}
          </WireframeSection>
        ) : null}

        <WireframeSection label="Offerta busta chiusa" testId="wireframe-region-auction-bid">
          {!marketOpen || (!isDemoMode && flow.currentSession?.status !== "open") ? (
            <UiStatePanel
              state="empty"
              title={marketOpen ? "Asta non aperta" : "Mercato chiuso"}
              message={
                marketOpen
                  ? flow.currentSession?.status === "scheduled"
                    ? `La sessione è programmata: si apre ${formatSessionDate(flow.currentSession.opensAt)} e chiude ${formatSessionDate(flow.currentSession.closesAt)}.`
                    : "Le offerte si possono inviare solo mentre la sessione è aperta."
                  : "L'amministratore ha chiuso il mercato. Restano disponibili solo gli scambi."
              }
              testId={marketOpen ? "auction-bid-not-open" : "auction-bid-market-closed"}
            />
          ) : (
            <AuctionBidPanel
              title="Nuova offerta"
              budgetLabel="Budget residuo"
              budgetValue={balance !== null ? `${balance} crediti` : "—"}
              playerLabel="Giocatore"
              playerPlaceholder="Scegli un giocatore…"
              playerField={
                isDemoMode ? undefined : (
                  <div className="fa-auction-panel__chooser">
                    <p className="fa-athlete-chooser__count">{loading ? "Caricamento calciatori…" : "Giocatore"}</p>
                    {loadError ? (
                      <UiStatePanel
                        state="error"
                        title="Listone non disponibile"
                        message={loadError}
                        testId="auction-listone-error"
                      />
                    ) : (
                      <AthleteChooser
                        testId="auction-bid-player"
                        entries={entries}
                        ownedAthleteIds={ownedAthleteIds}
                        selected={bidAthleteId ? [bidAthleteId] : []}
                        onToggle={(id) => setBidAthleteId(id === bidAthleteId ? "" : id)}
                        single
                      />
                    )}
                  </div>
                )
              }
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
            <Table compact className="fa-roster-table fa-auction-bids-table" data-testid="auction-my-bids-table">
              <TableHead>
                <TableRow>
                  <TableHeaderCell className="fa-roster-col fa-roster-col--name">
                    <RosterColLabel full="Giocatore" short="Nome" />
                  </TableHeaderCell>
                  <TableHeaderCell className="fa-roster-col fa-roster-col--credits">
                    <RosterColLabel full="Offerta" short="Cr" />
                  </TableHeaderCell>
                  <TableHeaderCell className="fa-roster-col fa-roster-col--status">Stato</TableHeaderCell>
                  <TableHeaderCell className="fa-roster-col fa-roster-col--action">
                    <RosterColLabel full="Azioni" short="" />
                  </TableHeaderCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {flow.myBids.map((bid) => (
                  <TableRow key={bid.id}>
                    <TableCell className="fa-roster-col fa-roster-col--name">
                      <AthleteName athleteId={bid.athleteId}>
                        {athleteNameById.get(bid.athleteId) ?? bid.athleteName}
                      </AthleteName>
                    </TableCell>
                    <TableCell className="fa-roster-col fa-roster-col--credits">
                      <RosterColLabel full={`${bid.amountCredits} crediti`} short={String(bid.amountCredits)} />
                    </TableCell>
                    <TableCell className="fa-roster-col fa-roster-col--status">
                      <Badge variant={bid.status === "submitted" ? "success" : "neutral"}>
                        {BID_STATUS_LABEL[bid.status]}
                      </Badge>
                    </TableCell>
                    <TableCell className="fa-roster-col fa-roster-col--action">
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

    </div>
  );
}
