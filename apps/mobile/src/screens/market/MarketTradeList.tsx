import type {
  FantasyRosterSlot,
  FantasyTeamSummary,
  RosterOccupancyEntry,
  TradeProposal,
} from "@fantappero/contracts";
import { HScroll } from "../../components/HScroll";
import { DateTimeField, formatDateTimeValue } from "../../components/DateTimeField";
import { useState } from "react";
import { Pressable, Text, View } from "react-native";
import { AthleteName } from "../../athletes/AthleteCard";
import { AppTextInput as TextInput } from "../../components/AppTextInput";
import { StatusBadge } from "../../components/StatusBadge";
import { UiStatePanel } from "../../components/UiStatePanel";
import { TRADE_STATUS_COLOR, TRADE_STATUS_LABEL } from "../../market/marketLabels";
import { marketUiStyles as styles } from "../../market/marketUiStyles";
import type { useTradeFlow } from "../../market/useTradeFlow";
import { CreditsDirectionField, PickPanel, type CreditsDirection, type TradeAthleteMeta } from "./MarketTradeCreateForm";

type TradeTab = "received" | "sent" | "open" | "all";
// "accepted" è già uno stato finale (execute_trade sposta subito giocatori e
// crediti quando non serve l'approvazione dell'amministratore). "countered"
// è altrettanto finale: segna la proposta ORIGINALE come superata — la vera
// proposta ancora da decidere è quella nuova (ruoli invertiti, stato
// "proposed") creata dalla controproposta, non questa riga storica.
const OPEN_STATUSES = new Set(["proposed", "pending_approval"]);

function TradeSide({
  title,
  athletes,
  credits,
}: {
  title: string;
  athletes: TradeProposal["offeredAthletes"];
  credits: number;
}) {
  return (
    <View style={{ gap: 6 }}>
      <Text style={styles.sideLabel}>{title}</Text>
      {athletes.length === 0 ? <Text style={styles.meta}>—</Text> : null}
      {athletes.map((athlete) => (
        <View key={athlete.id} style={styles.miniPlayer}>
          <AthleteName athleteId={athlete.id} style={styles.optionLabel}>
            {athlete.name}
          </AthleteName>
        </View>
      ))}
      {credits > 0 ? (
        <View style={styles.creditsChip}>
          <Text style={styles.creditsChipLabel}>{`+ ${credits} crediti`}</Text>
        </View>
      ) : null}
    </View>
  );
}

function toggleId(list: string[], id: string): string[] {
  return list.includes(id) ? list.filter((row) => row !== id) : [...list, id];
}

/** Elenco proposte di scambio inviate/ricevute con azioni e form di controproposta (EP08-05/06/07). */
export function MarketTradeList({
  trade,
  selfTeamId,
  teams,
  occupancy,
  athleteNameById,
  ownedSlots,
  canManageMarket,
  athleteMeta,
  highlightedProposalId,
}: {
  trade: ReturnType<typeof useTradeFlow>;
  selfTeamId: string | undefined;
  teams: FantasyTeamSummary[];
  occupancy: RosterOccupancyEntry[];
  athleteNameById: Map<string, string>;
  ownedSlots: FantasyRosterSlot[];
  canManageMarket: boolean;
  /** Ruolo e squadra di ogni calciatore, per il pannello di scelta nella controproposta. */
  athleteMeta: Map<string, TradeAthleteMeta>;
  /** Proposta aperta da una notifica: evidenziata invece di lasciarla cercare a mano. */
  highlightedProposalId?: string | null;
}) {
  const [tab, setTab] = useState<TradeTab>("open");
  const [counteringProposalId, setCounteringProposalId] = useState<string | null>(null);
  const [counterOfferedAthleteIds, setCounterOfferedAthleteIds] = useState<string[]>([]);
  const [counterRequestedAthleteIds, setCounterRequestedAthleteIds] = useState<string[]>([]);
  const [counterCreditsDirection, setCounterCreditsDirection] = useState<CreditsDirection>("offer");
  const [counterCreditsAmount, setCounterCreditsAmount] = useState("0");
  const [counterExpiresAt, setCounterExpiresAt] = useState("");

  function teamNameFor(teamId: string): string {
    if (selfTeamId === teamId) {
      return "La tua squadra";
    }
    return teams.find((row) => row.id === teamId)?.name ?? "Squadra";
  }

  function startCounter(proposalId: string) {
    setCounteringProposalId(proposalId);
    setCounterOfferedAthleteIds([]);
    setCounterRequestedAthleteIds([]);
    setCounterCreditsDirection("offer");
    setCounterCreditsAmount("0");
    setCounterExpiresAt("");
  }

  function handleCounterSubmit(proposalId: string) {
    // Scadenza facoltativa, come il form della proposta iniziale (e come sul web).
    let expiresIso: string | null = null;
    if (counterExpiresAt.trim()) {
      const parsed = new Date(counterExpiresAt.trim().replace(" ", "T"));
      if (Number.isNaN(parsed.getTime())) {
        return;
      }
      expiresIso = parsed.toISOString();
    }
    const credits = Number(counterCreditsAmount) || 0;
    void trade
      .counterProposal(proposalId, {
        offeredAthleteIds: counterOfferedAthleteIds,
        requestedAthleteIds: counterRequestedAthleteIds,
        offeredCredits: counterCreditsDirection === "offer" ? credits : 0,
        requestedCredits: counterCreditsDirection === "request" ? credits : 0,
        expiresAt: expiresIso,
      })
      .then(() => setCounteringProposalId(null));
  }

  const received = trade.proposals.filter(
    (row) => row.recipientTeamId === selfTeamId && OPEN_STATUSES.has(row.status),
  );
  const sent = trade.proposals.filter(
    (row) => row.proposerTeamId === selfTeamId && OPEN_STATUSES.has(row.status),
  );
  // Ancora da decidere, indipendentemente da chi l'ha proposta.
  const open = trade.proposals.filter((row) => OPEN_STATUSES.has(row.status));
  const visible =
    tab === "received"
      ? received
      : tab === "sent"
        ? sent
        : tab === "open"
          ? open
          : trade.proposals;
  const tabs: Array<{ id: TradeTab; label: string; count: number }> = [
    { id: "received", label: "Ricevute", count: received.length },
    { id: "sent", label: "Inviate", count: sent.length },
    { id: "open", label: "In corso", count: open.length },
    { id: "all", label: "Tutte", count: trade.proposals.length },
  ];

  return (
    <View style={{ gap: 12 }} testID="wireframe-region-market-trade">
      <HScroll testID="market-trade-tabs">
        {tabs.map((item) => (
          <Pressable
            key={item.id}
            style={[styles.pill, tab === item.id && styles.pillActive]}
            onPress={() => setTab(item.id)}
            accessibilityState={{ selected: tab === item.id }}
            testID={`market-trade-tab-${item.id}`}
          >
            <Text style={[styles.pillLabel, tab === item.id && styles.pillLabelActive]}>
              {item.count > 0 ? `${item.label} ${item.count}` : item.label}
            </Text>
          </Pressable>
        ))}
      </HScroll>

      {trade.loading ? (
        <UiStatePanel
          state="loading"
          title="Caricamento proposte"
          message="Recupero le proposte di scambio…"
          testID="market-trade-loading"
        />
      ) : null}

      {!trade.loading && trade.loadError ? (
        <UiStatePanel
          state="error"
          title="Proposte non disponibili"
          message={trade.loadError}
          testID="market-trade-load-error"
        />
      ) : null}

      {!trade.loading && !trade.loadError && visible.length === 0 ? (
        <UiStatePanel
          state="empty"
          title="Nessuna proposta"
          message={
            trade.proposals.length === 0
              ? "Non ci sono proposte di scambio inviate o ricevute."
              : "Nessuna proposta in questa sezione."
          }
          testID="market-trade-empty"
        />
      ) : null}

      {trade.actionError ? (
        <UiStatePanel
          state="error"
          title="Operazione non riuscita"
          message={trade.actionError}
          testID="market-trade-action-error"
        />
      ) : null}

      {!trade.loading && !trade.loadError && visible.length > 0 ? (
        <View testID="market-trade-list" style={{ gap: 12 }}>
          {visible.map((proposal) => {
            const isProposer = proposal.proposerTeamId === selfTeamId;
            const isRecipient = proposal.recipientTeamId === selfTeamId;
            const pending = trade.actionPendingId === proposal.id;
            const statusColor = TRADE_STATUS_COLOR[proposal.status];
            return (
              <View
                key={proposal.id}
                style={[
                  styles.proposalCard,
                  isRecipient && proposal.status === "proposed" && styles.proposalCardMine,
                  proposal.id === highlightedProposalId && styles.proposalCardHighlighted,
                ]}
                testID={`market-trade-proposal-${proposal.id}`}
              >
                <View style={styles.proposalHead}>
                  <View style={styles.proposalAvatar}>
                    <Text style={styles.proposalAvatarLabel}>
                      {teamNameFor(proposal.proposerTeamId).slice(0, 2).toUpperCase()}
                    </Text>
                  </View>
                  <Text style={styles.proposalTitle}>
                    {teamNameFor(proposal.proposerTeamId)} → {teamNameFor(proposal.recipientTeamId)}
                  </Text>
                  <StatusBadge
                    label={TRADE_STATUS_LABEL[proposal.status]}
                    color={statusColor.background}
                    textColor={statusColor.text}
                  />
                </View>
                {proposal.expiresAt ? (
                  <Text style={styles.meta}>
                    {`Scade il ${new Date(proposal.expiresAt).toLocaleString("it-IT", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" })}`}
                  </Text>
                ) : null}
                <TradeSide title="Offre" athletes={proposal.offeredAthletes} credits={proposal.offeredCredits} />
                <View style={styles.swapBadge}>
                  <Text style={styles.swapBadgeLabel}>⇅</Text>
                </View>
                <TradeSide title="Chiede" athletes={proposal.requestedAthletes} credits={proposal.requestedCredits} />

                {proposal.status === "proposed" && isProposer ? (
                  <Pressable
                    style={[styles.secondaryButton, pending && styles.disabled]}
                    disabled={pending}
                    onPress={() => void trade.cancelProposal(proposal.id)}
                    testID={`market-trade-cancel-${proposal.id}`}
                  >
                    <Text style={styles.secondaryButtonLabel}>Annulla</Text>
                  </Pressable>
                ) : null}

                {proposal.status === "proposed" && isRecipient ? (
                  <View style={styles.tradeActions}>
                    <Pressable
                      style={[styles.button, styles.tradeAction, pending && styles.disabled]}
                      disabled={pending}
                      onPress={() => void trade.acceptProposal(proposal.id)}
                      testID={`market-trade-accept-${proposal.id}`}
                    >
                      <Text style={styles.buttonLabel} numberOfLines={1} adjustsFontSizeToFit>Accetta</Text>
                    </Pressable>
                    <Pressable
                      style={[styles.secondaryButton, styles.tradeAction, pending && styles.disabled]}
                      disabled={pending}
                      onPress={() => {
                        setCounteringProposalId((current) =>
                          current === proposal.id ? null : current,
                        );
                        void trade.rejectProposal(proposal.id);
                      }}
                      testID={`market-trade-reject-${proposal.id}`}
                    >
                      <Text style={styles.secondaryButtonLabel} numberOfLines={1} adjustsFontSizeToFit>Rifiuta</Text>
                    </Pressable>
                    <Pressable
                      style={[
                        styles.secondaryButton,
                        styles.tradeAction,
                        (pending || ownedSlots.length === 0) && styles.disabled,
                      ]}
                      disabled={pending || ownedSlots.length === 0}
                      onPress={() => startCounter(proposal.id)}
                      testID={`market-trade-counter-start-${proposal.id}`}
                    >
                      <Text style={styles.secondaryButtonLabel} numberOfLines={1} adjustsFontSizeToFit>Controproponi</Text>
                    </Pressable>
                  </View>
                ) : null}

                {proposal.status === "pending_approval" && canManageMarket ? (
                  <View style={styles.rowActions} testID={`market-trade-admin-actions-${proposal.id}`}>
                    <Pressable
                      style={[styles.button, pending && styles.disabled]}
                      disabled={pending}
                      onPress={() => void trade.approveProposal(proposal.id)}
                      testID={`market-trade-approve-${proposal.id}`}
                    >
                      <Text style={styles.buttonLabel}>Approva</Text>
                    </Pressable>
                    <Pressable
                      style={[styles.secondaryButton, pending && styles.disabled]}
                      disabled={pending}
                      onPress={() => void trade.rejectProposalAsAdmin(proposal.id)}
                      testID={`market-trade-reject-admin-${proposal.id}`}
                    >
                      <Text style={styles.secondaryButtonLabel}>Rifiuta (admin)</Text>
                    </Pressable>
                  </View>
                ) : null}

                {counteringProposalId === proposal.id ? (
                  <View style={styles.field} testID={`market-trade-counter-form-${proposal.id}`}>
                    <PickPanel
                      testID={`market-trade-counter-offered-${proposal.id}`}
                      title="Tu dai (controproposta)"
                      hint="Scegli uno o più giocatori della tua rosa"
                      rows={ownedSlots.map((slot) => ({
                        athleteId: slot.athleteId as string,
                        name: slot.athleteName ?? "Giocatore",
                        price: slot.purchaseCredits ?? null,
                      }))}
                      selected={counterOfferedAthleteIds}
                      onToggle={(id) => setCounterOfferedAthleteIds((prev) => toggleId(prev, id))}
                      meta={athleteMeta}
                      emptyText="Nessun giocatore in rosa da offrire."
                    />

                    <PickPanel
                      testID={`market-trade-counter-requested-${proposal.id}`}
                      title="Tu ricevi (controproposta)"
                      hint={`Scegli uno o più giocatori di ${teamNameFor(proposal.proposerTeamId)}`}
                      rows={occupancy
                        .filter((entry) => entry.fantasyTeamId === proposal.proposerTeamId)
                        .map((entry) => ({
                          athleteId: entry.athleteId,
                          name: entry.athleteName ?? athleteNameById.get(entry.athleteId) ?? "Giocatore",
                          price: entry.purchaseCredits,
                        }))}
                      selected={counterRequestedAthleteIds}
                      onToggle={(id) => setCounterRequestedAthleteIds((prev) => toggleId(prev, id))}
                      meta={athleteMeta}
                      emptyText="Questa squadra non ha ancora giocatori in rosa."
                    />

                    <CreditsDirectionField
                      direction={counterCreditsDirection}
                      amount={counterCreditsAmount}
                      onDirectionChange={setCounterCreditsDirection}
                      onAmountChange={setCounterCreditsAmount}
                      testIDPrefix="market-trade-counter"
                    />
                    <DateTimeField
                      label="Scadenza"
                      value={counterExpiresAt}
                      onChange={setCounterExpiresAt}
                      placeholder="Scegli quando scade la proposta"
                      min={formatDateTimeValue(new Date())}
                      minHint="La scadenza deve essere futura"
                    />
                    <View style={styles.rowActions}>
                      <Pressable
                        style={[styles.button, pending && styles.disabled]}
                        disabled={pending}
                        onPress={() => handleCounterSubmit(proposal.id)}
                        testID={`market-trade-counter-submit-${proposal.id}`}
                      >
                        <Text style={styles.buttonLabel}>Invia controproposta</Text>
                      </Pressable>
                      <Pressable
                        style={styles.secondaryButton}
                        onPress={() => setCounteringProposalId(null)}
                      >
                        <Text style={styles.secondaryButtonLabel}>Annulla</Text>
                      </Pressable>
                    </View>
                  </View>
                ) : null}
              </View>
            );
          })}
        </View>
      ) : null}
    </View>
  );
}
