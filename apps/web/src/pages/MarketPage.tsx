import type {
  FantasyTeam,
  FantasyTeamSummary,
  LeagueListoneEntry,
  MarketHistoryCategory,
  MarketReleasePreview,
  MarketReleaseReason,
  RosterOccupancyEntry,
  TeamRosterPlayer,
} from "@fantappero/contracts";
import {
  Badge,
  Breadcrumb,
  Button,
  Input,
  PageContainer,
  Select,
  UiStatePanel,
  WireframeSection,
} from "@fantappero/ui";
import { type FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { applyVoluntaryRelease, previewVoluntaryRelease } from "../api/market";
import {
  fetchFantasyTeams,
  fetchLeagueListone,
  fetchMyCredits,
  fetchMyFantasyTeam,
  fetchRosterOccupancy,
  fetchTeamPlayersForTrade,
} from "../api/leagues";
import { getApiErrorMessage, useAuth } from "../auth/AuthContext";
import { loadStoredSession } from "../auth/sessionStorage";
import { useMarketHistory } from "../market/useMarketHistory";
import { useTradeFlow } from "../market/useTradeFlow";
import { useLocation } from "../router/simpleRouter";
import { parseWireframeStateFromSearch } from "../wireframes/useWireframeState";

const HISTORY_CATEGORY_OPTIONS = [
  { value: "acquisto", label: "Acquisto" },
  { value: "svincolo", label: "Svincolo" },
  { value: "scambio", label: "Scambio" },
  { value: "intervento_manuale", label: "Intervento manuale" },
];

const TRADE_STATUS_LABEL: Record<string, string> = {
  proposed: "Proposta",
  cancelled: "Annullata",
  expired: "Scaduta",
  accepted: "Accettata",
  rejected: "Rifiutata",
  countered: "Controproposta ricevuta",
  pending_approval: "In attesa di approvazione",
  executed: "Eseguita",
  rejected_by_admin: "Rifiutata dall'amministratore",
};

const TRADE_STATUS_VARIANT: Record<string, "success" | "warning" | "accent" | "danger" | "neutral"> = {
  proposed: "accent",
  cancelled: "neutral",
  expired: "neutral",
  accepted: "success",
  rejected: "danger",
  countered: "warning",
  pending_approval: "warning",
  executed: "success",
  rejected_by_admin: "danger",
};

const REASON_OPTIONS: Array<{ value: MarketReleaseReason; label: string }> = [
  { value: "voluntary", label: "Svincolo volontario" },
  { value: "league_exit", label: "Uscita dai cinque campionati" },
];

const DEMO_TEAM: FantasyTeam = {
  id: "demo-team",
  leagueId: "demo-league",
  membershipId: "demo-membership",
  userId: "demo-user",
  userType: "human",
  name: "Squadra Demo",
  rosterSize: 25,
  filledSlots: 1,
  compositionStatus: "incomplete",
  slots: [
    {
      id: "demo-slot-0",
      slotIndex: 0,
      athleteId: "demo-athlete-1",
      athleteName: "P. Fagioli",
      clubName: "Juventus",
      role: "C",
      purchaseCredits: 12,
    },
  ],
};

/** Schermata Mercato: svincolo volontario con recupero crediti (EP08-04 / FR-MKT-02). */
export function MarketPage() {
  const { isDemoMode, activeLeagueId, can } = useAuth();
  const canManageMarket = can(["market:manage"]);
  const { search } = useLocation();
  const demoState = isDemoMode ? parseWireframeStateFromSearch(search) : null;

  const [team, setTeam] = useState<FantasyTeam | null>(isDemoMode ? DEMO_TEAM : null);
  const [balance, setBalance] = useState<number | null>(isDemoMode ? 200 : null);
  const [teams, setTeams] = useState<FantasyTeamSummary[]>([]);
  const [occupancy, setOccupancy] = useState<RosterOccupancyEntry[]>([]);
  const [listoneEntries, setListoneEntries] = useState<LeagueListoneEntry[]>([]);
  const [loading, setLoading] = useState(() => (isDemoMode ? demoState === "loading" : true));
  const [loadError, setLoadError] = useState<string | null>(() =>
    isDemoMode && demoState === "error" ? "Impossibile caricare la rosa (demo)." : null,
  );

  const loadTeam = useCallback(async () => {
    if (isDemoMode) {
      setTeam(
        demoState === "empty" || demoState === "error" || demoState === "forbidden"
          ? { ...DEMO_TEAM, slots: [] }
          : DEMO_TEAM,
      );
      setLoading(demoState === "loading");
      setLoadError(demoState === "error" ? "Impossibile caricare la rosa (demo)." : null);
      return;
    }
    if (!activeLeagueId) {
      setLoading(false);
      setTeam(null);
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
      const [myTeam, credits, allTeams, allOccupancy, listone] = await Promise.all([
        fetchMyFantasyTeam(stored.accessToken, activeLeagueId),
        fetchMyCredits(stored.accessToken, activeLeagueId).catch(() => null),
        fetchFantasyTeams(stored.accessToken, activeLeagueId).catch(() => []),
        fetchRosterOccupancy(stored.accessToken, activeLeagueId).catch(() => []),
        fetchLeagueListone(stored.accessToken, activeLeagueId).catch(() => []),
      ]);
      setTeam(myTeam);
      if (credits) {
        setBalance(credits.balance);
      }
      setTeams(allTeams);
      setOccupancy(allOccupancy);
      setListoneEntries(listone);
    } catch (error) {
      setTeam(null);
      setLoadError(getApiErrorMessage(error, "Impossibile caricare la rosa."));
    } finally {
      setLoading(false);
    }
  }, [activeLeagueId, demoState, isDemoMode]);

  useEffect(() => {
    void loadTeam();
  }, [loadTeam]);

  const athleteNameById = useMemo(() => {
    const map = new Map<string, string>();
    for (const entry of listoneEntries) {
      map.set(entry.athleteId, entry.canonicalName);
    }
    return map;
  }, [listoneEntries]);

  const otherTeams = useMemo(() => teams.filter((row) => row.id !== team?.id), [teams, team]);

  const trade = useTradeFlow({ leagueId: activeLeagueId, active: !isDemoMode });
  const history = useMarketHistory({ leagueId: activeLeagueId, active: !isDemoMode });

  const ownedSlots = useMemo(
    () => (team?.slots ?? []).filter((slot) => slot.athleteId !== null),
    [team],
  );

  const slotOptions = useMemo(
    () =>
      ownedSlots.map((slot) => ({
        value: String(slot.slotIndex),
        label: `${slot.athleteName} (${slot.purchaseCredits ?? 0} crediti)`,
      })),
    [ownedSlots],
  );

  const [selectedSlotIndex, setSelectedSlotIndex] = useState("");
  const [reason, setReason] = useState<MarketReleaseReason>("voluntary");
  const [preview, setPreview] = useState<MarketReleasePreview | null>(null);
  const [previewError, setPreviewError] = useState<string | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [applyError, setApplyError] = useState<string | null>(null);
  const [applySuccess, setApplySuccess] = useState<string | null>(null);
  const [applying, setApplying] = useState(false);

  async function handlePreview() {
    if (isDemoMode || !activeLeagueId || selectedSlotIndex === "") {
      return;
    }
    const stored = loadStoredSession();
    if (!stored?.accessToken) {
      setPreviewError("Sessione non disponibile. Accedi di nuovo.");
      return;
    }
    setPreviewLoading(true);
    setPreviewError(null);
    setPreview(null);
    setApplySuccess(null);
    try {
      const result = await previewVoluntaryRelease(
        stored.accessToken,
        activeLeagueId,
        Number(selectedSlotIndex),
        reason,
      );
      setPreview(result);
    } catch (error) {
      setPreviewError(getApiErrorMessage(error, "Impossibile calcolare il rimborso."));
    } finally {
      setPreviewLoading(false);
    }
  }

  async function handleApply() {
    if (isDemoMode || !activeLeagueId || selectedSlotIndex === "") {
      return;
    }
    const stored = loadStoredSession();
    if (!stored?.accessToken) {
      setApplyError("Sessione non disponibile. Accedi di nuovo.");
      return;
    }
    setApplying(true);
    setApplyError(null);
    try {
      const result = await applyVoluntaryRelease(
        stored.accessToken,
        activeLeagueId,
        Number(selectedSlotIndex),
        reason,
      );
      setBalance(result.balance);
      setApplySuccess(
        `${result.athleteName} svincolato: rimborsati ${result.refundCredits} crediti.`,
      );
      setPreview(null);
      setSelectedSlotIndex("");
      await loadTeam();
    } catch (error) {
      setApplyError(getApiErrorMessage(error, "Impossibile completare lo svincolo."));
    } finally {
      setApplying(false);
    }
  }

  // -- Scambi tra partecipanti (EP08-05/06) ------------------------------------

  const [recipientTeamId, setRecipientTeamId] = useState("");
  const [recipientPlayers, setRecipientPlayers] = useState<TeamRosterPlayer[]>([]);
  const [recipientRosterLoading, setRecipientRosterLoading] = useState(false);
  const [recipientRosterError, setRecipientRosterError] = useState<string | null>(null);
  const [offeredAthleteIds, setOfferedAthleteIds] = useState<string[]>([]);
  const [requestedAthleteIds, setRequestedAthleteIds] = useState<string[]>([]);
  const [offeredCredits, setOfferedCredits] = useState("0");
  const [requestedCredits, setRequestedCredits] = useState("0");
  const [expiresAt, setExpiresAt] = useState("");

  const recipientOptions = useMemo(
    () => otherTeams.map((row) => ({ value: row.id, label: row.name })),
    [otherTeams],
  );

  const loadRecipientRoster = useCallback(
    async (teamId: string) => {
      if (!teamId || !activeLeagueId || isDemoMode) {
        setRecipientPlayers([]);
        setRecipientRosterLoading(false);
        setRecipientRosterError(null);
        return;
      }
      const stored = loadStoredSession();
      if (!stored?.accessToken) {
        setRecipientPlayers([]);
        setRecipientRosterError("Sessione non disponibile. Accedi di nuovo.");
        return;
      }
      setRecipientRosterLoading(true);
      setRecipientRosterError(null);
      try {
        const players = await fetchTeamPlayersForTrade(
          stored.accessToken,
          activeLeagueId,
          teamId,
        );
        setRecipientPlayers(players);
      } catch (error) {
        setRecipientPlayers([]);
        setRecipientRosterError(
          getApiErrorMessage(error, "Impossibile caricare la rosa della squadra selezionata."),
        );
      } finally {
        setRecipientRosterLoading(false);
      }
    },
    [activeLeagueId, isDemoMode],
  );

  function toggleAthleteId(list: string[], id: string): string[] {
    return list.includes(id) ? list.filter((row) => row !== id) : [...list, id];
  }

  function resetTradeForm() {
    setRecipientTeamId("");
    setRecipientPlayers([]);
    setRecipientRosterError(null);
    setOfferedAthleteIds([]);
    setRequestedAthleteIds([]);
    setOfferedCredits("0");
    setRequestedCredits("0");
    setExpiresAt("");
  }

  function handleCreateProposal(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!recipientTeamId || !expiresAt) {
      return;
    }
    void trade
      .createProposal({
        recipientTeamId,
        offeredAthleteIds,
        requestedAthleteIds,
        offeredCredits: Number(offeredCredits) || 0,
        requestedCredits: Number(requestedCredits) || 0,
        expiresAt: new Date(expiresAt).toISOString(),
      })
      .then(resetTradeForm);
  }

  const [counteringProposalId, setCounteringProposalId] = useState<string | null>(null);
  const [counterOfferedAthleteIds, setCounterOfferedAthleteIds] = useState<string[]>([]);
  const [counterRequestedAthleteIds, setCounterRequestedAthleteIds] = useState<string[]>([]);
  const [counterOfferedCredits, setCounterOfferedCredits] = useState("0");
  const [counterRequestedCredits, setCounterRequestedCredits] = useState("0");
  const [counterExpiresAt, setCounterExpiresAt] = useState("");

  function startCounter(proposalId: string) {
    setCounteringProposalId(proposalId);
    setCounterOfferedAthleteIds([]);
    setCounterRequestedAthleteIds([]);
    setCounterOfferedCredits("0");
    setCounterRequestedCredits("0");
    setCounterExpiresAt("");
  }

  function handleCounterSubmit(event: FormEvent<HTMLFormElement>, proposalId: string) {
    event.preventDefault();
    if (!counterExpiresAt) {
      return;
    }
    void trade
      .counterProposal(proposalId, {
        offeredAthleteIds: counterOfferedAthleteIds,
        requestedAthleteIds: counterRequestedAthleteIds,
        offeredCredits: Number(counterOfferedCredits) || 0,
        requestedCredits: Number(counterRequestedCredits) || 0,
        expiresAt: new Date(counterExpiresAt).toISOString(),
      })
      .then(() => setCounteringProposalId(null));
  }

  function teamNameFor(teamId: string): string {
    if (team?.id === teamId) {
      return "La tua squadra";
    }
    return teams.find((row) => row.id === teamId)?.name ?? "Squadra";
  }

  if (isDemoMode && demoState === "forbidden") {
    return (
      <PageContainer
        title="Mercato"
        header={<Breadcrumb items={[{ label: "Leghe", href: "/leghe" }, { label: "Mercato" }]} />}
      >
        <UiStatePanel
          state="forbidden"
          title="Permessi insufficienti"
          message="Non hai accesso al mercato di questa lega."
          testId="wireframe-market-forbidden"
        />
      </PageContainer>
    );
  }

  return (
    <PageContainer
      title="Mercato"
      header={<Breadcrumb items={[{ label: "Leghe", href: "/leghe" }, { label: "Mercato" }]} />}
    >
      <div className="fa-market-page">
        {loading ? (
          <UiStatePanel
            state="loading"
            title="Caricamento"
            message="Recupero la tua rosa…"
            testId="wireframe-market-loading"
          />
        ) : null}

        {!loading && loadError ? (
          <>
            <UiStatePanel
              state="error"
              title="Rosa non disponibile"
              message={loadError}
              testId="wireframe-market-error"
            />
            <Button variant="secondary" onClick={() => void loadTeam()}>
              Ricarica
            </Button>
          </>
        ) : null}

        {!loading && !loadError && !isDemoMode && !activeLeagueId ? (
          <UiStatePanel
            state="empty"
            title="Nessuna lega selezionata"
            message="Scegli una lega per accedere al mercato."
            testId="wireframe-market-no-league"
          />
        ) : null}

        {!loading && !loadError && (isDemoMode || activeLeagueId) ? (
          <WireframeSection label="Svincolo volontario" testId="market-release-section">
            {ownedSlots.length === 0 ? (
              <UiStatePanel
                state="empty"
                title="Nessun giocatore da svincolare"
                message="La tua rosa non ha ancora giocatori assegnati."
                testId="wireframe-market-success"
              />
            ) : (
              <div data-testid="wireframe-market-success">
                <p>Budget residuo: {balance !== null ? `${balance} crediti` : "—"}</p>
                <Select
                  label="Giocatore da svincolare"
                  name="release-slot"
                  options={slotOptions}
                  placeholder="Scegli un giocatore…"
                  value={isDemoMode ? undefined : selectedSlotIndex}
                  onChange={
                    isDemoMode
                      ? undefined
                      : (event) => {
                          setSelectedSlotIndex(event.target.value);
                          setPreview(null);
                          setApplySuccess(null);
                        }
                  }
                  disabled={isDemoMode}
                />
                <Select
                  label="Motivo"
                  name="release-reason"
                  options={REASON_OPTIONS}
                  value={isDemoMode ? undefined : reason}
                  onChange={
                    isDemoMode
                      ? undefined
                      : (event) => {
                          setReason(event.target.value as MarketReleaseReason);
                          setPreview(null);
                        }
                  }
                  disabled={isDemoMode}
                />

                <div className="fa-ds-showcase__row">
                  <Button
                    variant="secondary"
                    disabled={isDemoMode || selectedSlotIndex === "" || previewLoading}
                    onClick={() => void handlePreview()}
                  >
                    {previewLoading ? "Calcolo…" : "Calcola rimborso"}
                  </Button>
                  <Button
                    variant="primary"
                    disabled={isDemoMode || !preview || applying}
                    onClick={() => void handleApply()}
                  >
                    {applying ? "Conferma…" : "Conferma svincolo"}
                  </Button>
                </div>

                {previewError ? (
                  <UiStatePanel
                    state="error"
                    title="Anteprima non disponibile"
                    message={previewError}
                    testId="market-release-preview-error"
                  />
                ) : null}

                {preview ? (
                  <p data-testid="market-release-preview">
                    Rimborso stimato: {preview.refundCredits} crediti ({preview.refundPercent}% di{" "}
                    {preview.purchaseCredits})
                  </p>
                ) : null}

                {applyError ? (
                  <UiStatePanel
                    state="error"
                    title="Svincolo non riuscito"
                    message={applyError}
                    testId="market-release-apply-error"
                  />
                ) : null}

                {applySuccess ? (
                  <UiStatePanel
                    state="success"
                    title="Fatto"
                    message={applySuccess}
                    testId="market-release-apply-success"
                  />
                ) : null}
              </div>
            )}
          </WireframeSection>
        ) : null}

        {!loading && !loadError && !isDemoMode && activeLeagueId ? (
          <WireframeSection label="Nuova proposta di scambio" testId="market-trade-form-section">
            <form data-testid="market-trade-create-form" onSubmit={handleCreateProposal}>
              <Select
                label="Squadra destinataria"
                name="trade-recipient"
                options={recipientOptions}
                placeholder="Scegli una squadra…"
                value={recipientTeamId}
                onChange={(event) => {
                  const nextId = event.target.value;
                  setRecipientTeamId(nextId);
                  setRequestedAthleteIds([]);
                  void loadRecipientRoster(nextId);
                }}
                required
              />

              <fieldset data-testid="market-trade-offered-athletes">
                <legend>Giocatori offerti (dalla tua rosa)</legend>
                {ownedSlots.length === 0 ? (
                  <p>Nessun giocatore in rosa da offrire.</p>
                ) : (
                  ownedSlots.map((slot) => (
                    <label key={slot.id}>
                      <input
                        type="checkbox"
                        checked={offeredAthleteIds.includes(slot.athleteId as string)}
                        onChange={() =>
                          setOfferedAthleteIds((prev) =>
                            toggleAthleteId(prev, slot.athleteId as string),
                          )
                        }
                      />{" "}
                      {slot.athleteName}
                    </label>
                  ))
                )}
              </fieldset>

              <fieldset data-testid="market-trade-requested-athletes">
                <legend>Giocatori richiesti</legend>
                {!recipientTeamId ? (
                  <p>Scegli prima una squadra destinataria.</p>
                ) : null}
                {recipientTeamId && recipientRosterLoading ? (
                  <UiStatePanel
                    state="loading"
                    title="Caricamento rosa"
                    message="Recupero i giocatori della squadra selezionata…"
                    testId="market-trade-recipient-loading"
                  />
                ) : null}
                {recipientTeamId && !recipientRosterLoading && recipientRosterError ? (
                  <div>
                    <UiStatePanel
                      state="error"
                      title="Rosa non disponibile"
                      message={recipientRosterError}
                      testId="market-trade-recipient-error"
                    />
                    <Button
                      type="button"
                      variant="ghost"
                      onClick={() => void loadRecipientRoster(recipientTeamId)}
                    >
                      Riprova
                    </Button>
                  </div>
                ) : null}
                {recipientTeamId &&
                !recipientRosterLoading &&
                !recipientRosterError &&
                recipientPlayers.length === 0 ? (
                  <p data-testid="market-trade-recipient-empty">
                    Questa squadra non ha ancora giocatori in rosa.
                  </p>
                ) : null}
                {recipientTeamId &&
                !recipientRosterLoading &&
                !recipientRosterError &&
                recipientPlayers.length > 0
                  ? recipientPlayers.map((athlete) => (
                      <label key={athlete.athleteId}>
                        <input
                          type="checkbox"
                          checked={requestedAthleteIds.includes(athlete.athleteId)}
                          onChange={() =>
                            setRequestedAthleteIds((prev) =>
                              toggleAthleteId(prev, athlete.athleteId),
                            )
                          }
                        />{" "}
                        {athlete.athleteName}
                      </label>
                    ))
                  : null}
              </fieldset>

              <Input
                label="Crediti offerti"
                name="trade-offered-credits"
                type="number"
                min={0}
                value={offeredCredits}
                onChange={(event) => setOfferedCredits(event.target.value)}
              />
              <Input
                label="Crediti richiesti"
                name="trade-requested-credits"
                type="number"
                min={0}
                value={requestedCredits}
                onChange={(event) => setRequestedCredits(event.target.value)}
              />
              <Input
                label="Scadenza"
                name="trade-expires-at"
                type="datetime-local"
                value={expiresAt}
                onChange={(event) => setExpiresAt(event.target.value)}
                required
              />

              {trade.createError ? (
                <UiStatePanel
                  state="error"
                  title="Proposta non inviata"
                  message={trade.createError}
                  testId="market-trade-create-error"
                />
              ) : null}

              <Button type="submit" variant="primary" disabled={trade.creating}>
                {trade.creating ? "Invio…" : "Proponi scambio"}
              </Button>
            </form>
          </WireframeSection>
        ) : null}

        {!isDemoMode && activeLeagueId ? (
          <WireframeSection label="Proposte di scambio" testId="wireframe-region-market-trade">
            {trade.loading ? (
              <UiStatePanel
                state="loading"
                title="Caricamento proposte"
                message="Recupero le proposte di scambio…"
                testId="market-trade-loading"
              />
            ) : null}

            {!trade.loading && trade.loadError ? (
              <UiStatePanel
                state="error"
                title="Proposte non disponibili"
                message={trade.loadError}
                testId="market-trade-load-error"
              />
            ) : null}

            {!trade.loading && !trade.loadError && trade.proposals.length === 0 ? (
              <UiStatePanel
                state="empty"
                title="Nessuna proposta"
                message="Non ci sono proposte di scambio inviate o ricevute."
                testId="market-trade-empty"
              />
            ) : null}

            {trade.actionError ? (
              <UiStatePanel
                state="error"
                title="Operazione non riuscita"
                message={trade.actionError}
                testId="market-trade-action-error"
              />
            ) : null}

            {!trade.loading && !trade.loadError && trade.proposals.length > 0 ? (
              <ul data-testid="market-trade-list">
                {trade.proposals.map((proposal) => {
                  const isProposer = proposal.proposerTeamId === team?.id;
                  const isRecipient = proposal.recipientTeamId === team?.id;
                  const pending = trade.actionPendingId === proposal.id;
                  return (
                    <li key={proposal.id} data-testid={`market-trade-proposal-${proposal.id}`}>
                      <p>
                        {teamNameFor(proposal.proposerTeamId)} → {teamNameFor(proposal.recipientTeamId)}{" "}
                        <Badge variant={TRADE_STATUS_VARIANT[proposal.status] ?? "neutral"}>
                          {TRADE_STATUS_LABEL[proposal.status] ?? proposal.status}
                        </Badge>
                      </p>
                      <p>
                        Offerti: {proposal.offeredAthletes.map((a) => a.name).join(", ") || "—"}
                        {proposal.offeredCredits > 0 ? ` + ${proposal.offeredCredits} crediti` : ""}
                      </p>
                      <p>
                        Richiesti: {proposal.requestedAthletes.map((a) => a.name).join(", ") || "—"}
                        {proposal.requestedCredits > 0 ? ` + ${proposal.requestedCredits} crediti` : ""}
                      </p>

                      {proposal.status === "proposed" && isProposer ? (
                        <Button
                          variant="secondary"
                          size="sm"
                          disabled={pending}
                          onClick={() => void trade.cancelProposal(proposal.id)}
                        >
                          Annulla
                        </Button>
                      ) : null}

                      {proposal.status === "proposed" && isRecipient ? (
                        <div className="fa-ds-showcase__row">
                          <Button
                            variant="primary"
                            size="sm"
                            disabled={pending}
                            onClick={() => void trade.acceptProposal(proposal.id)}
                          >
                            Accetta
                          </Button>
                          <Button
                            variant="secondary"
                            size="sm"
                            disabled={pending}
                            onClick={() => void trade.rejectProposal(proposal.id)}
                          >
                            Rifiuta
                          </Button>
                          <Button
                            variant="secondary"
                            size="sm"
                            disabled={pending}
                            onClick={() => startCounter(proposal.id)}
                          >
                            Controproponi
                          </Button>
                        </div>
                      ) : null}

                      {proposal.status === "pending_approval" && canManageMarket ? (
                        <div className="fa-ds-showcase__row" data-testid={`market-trade-admin-actions-${proposal.id}`}>
                          <Button
                            variant="primary"
                            size="sm"
                            disabled={pending}
                            onClick={() => void trade.approveProposal(proposal.id)}
                          >
                            Approva
                          </Button>
                          <Button
                            variant="secondary"
                            size="sm"
                            disabled={pending}
                            onClick={() => void trade.rejectProposalAsAdmin(proposal.id)}
                          >
                            Rifiuta (admin)
                          </Button>
                        </div>
                      ) : null}

                      {counteringProposalId === proposal.id ? (
                        <form
                          data-testid={`market-trade-counter-form-${proposal.id}`}
                          onSubmit={(event) => handleCounterSubmit(event, proposal.id)}
                        >
                          <fieldset>
                            <legend>Giocatori offerti nella controproposta</legend>
                            {ownedSlots.map((slot) => (
                              <label key={slot.id}>
                                <input
                                  type="checkbox"
                                  checked={counterOfferedAthleteIds.includes(
                                    slot.athleteId as string,
                                  )}
                                  onChange={() =>
                                    setCounterOfferedAthleteIds((prev) =>
                                      toggleAthleteId(prev, slot.athleteId as string),
                                    )
                                  }
                                />{" "}
                                {slot.athleteName}
                              </label>
                            ))}
                          </fieldset>
                          <fieldset>
                            <legend>Giocatori richiesti nella controproposta</legend>
                            {occupancy
                              .filter((entry) => entry.fantasyTeamId === proposal.proposerTeamId)
                              .map((entry) => (
                                <label key={entry.athleteId}>
                                  <input
                                    type="checkbox"
                                    checked={counterRequestedAthleteIds.includes(entry.athleteId)}
                                    onChange={() =>
                                      setCounterRequestedAthleteIds((prev) =>
                                        toggleAthleteId(prev, entry.athleteId),
                                      )
                                    }
                                  />{" "}
                                  {entry.athleteName ??
                                    athleteNameById.get(entry.athleteId) ??
                                    "Giocatore"}
                                </label>
                              ))}
                          </fieldset>
                          <Input
                            label="Crediti offerti"
                            name="counter-offered-credits"
                            type="number"
                            min={0}
                            value={counterOfferedCredits}
                            onChange={(event) => setCounterOfferedCredits(event.target.value)}
                          />
                          <Input
                            label="Crediti richiesti"
                            name="counter-requested-credits"
                            type="number"
                            min={0}
                            value={counterRequestedCredits}
                            onChange={(event) => setCounterRequestedCredits(event.target.value)}
                          />
                          <Input
                            label="Scadenza"
                            name="counter-expires-at"
                            type="datetime-local"
                            value={counterExpiresAt}
                            onChange={(event) => setCounterExpiresAt(event.target.value)}
                            required
                          />
                          <div className="fa-ds-showcase__row">
                            <Button type="submit" variant="primary" disabled={pending}>
                              Invia controproposta
                            </Button>
                            <Button
                              type="button"
                              variant="secondary"
                              onClick={() => setCounteringProposalId(null)}
                            >
                              Annulla
                            </Button>
                          </div>
                        </form>
                      ) : null}
                    </li>
                  );
                })}
              </ul>
            ) : null}
          </WireframeSection>
        ) : null}

        {!isDemoMode && activeLeagueId ? (
          <WireframeSection label="Storico mercato" testId="wireframe-region-market-history">
            <div className="fa-ds-showcase__row">
              <Select
                label="Categoria"
                name="history-category"
                options={HISTORY_CATEGORY_OPTIONS}
                placeholder="Tutte le categorie"
                value={history.category}
                onChange={(event) =>
                  history.setCategory(event.target.value as MarketHistoryCategory | "")
                }
              />
              <Select
                label="Squadra"
                name="history-team"
                options={teams.map((row) => ({ value: row.id, label: row.name }))}
                placeholder="Tutte le squadre"
                value={history.fantasyTeamId}
                onChange={(event) => history.setFantasyTeamId(event.target.value)}
              />
            </div>

            {history.loading ? (
              <UiStatePanel
                state="loading"
                title="Caricamento storico"
                message="Recupero gli eventi di mercato…"
                testId="market-history-loading"
              />
            ) : null}

            {!history.loading && history.loadError ? (
              <UiStatePanel
                state="error"
                title="Storico non disponibile"
                message={history.loadError}
                testId="market-history-error"
              />
            ) : null}

            {!history.loading && !history.loadError && history.items.length === 0 ? (
              <UiStatePanel
                state="empty"
                title="Nessun evento"
                message="Non ci sono eventi di mercato per i filtri selezionati."
                testId="market-history-empty"
              />
            ) : null}

            {!history.loading && !history.loadError && history.items.length > 0 ? (
              <>
                <ul data-testid="market-history-list">
                  {history.items.map((entry) => (
                    <li key={entry.id} data-testid={`market-history-entry-${entry.id}`}>
                      <Badge variant="neutral">{entry.category}</Badge> {entry.action} —{" "}
                      {new Date(entry.occurredAt).toLocaleString("it-IT")}
                    </li>
                  ))}
                </ul>
                <div className="fa-ds-showcase__row">
                  <Button
                    variant="secondary"
                    disabled={history.page <= 1}
                    onClick={() => history.goToPage(history.page - 1)}
                  >
                    Pagina precedente
                  </Button>
                  <span>
                    Pagina {history.page} di {history.totalPages} ({history.total} eventi)
                  </span>
                  <Button
                    variant="secondary"
                    disabled={history.page >= history.totalPages}
                    onClick={() => history.goToPage(history.page + 1)}
                  >
                    Pagina successiva
                  </Button>
                </div>
              </>
            ) : null}
          </WireframeSection>
        ) : null}
      </div>
    </PageContainer>
  );
}
