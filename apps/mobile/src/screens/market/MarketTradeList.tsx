import type {
  FantasyRosterSlot,
  FantasyTeamSummary,
  RosterOccupancyEntry,
  TradeProposal,
} from "@fantappero/contracts";
import { useState } from "react";
import { Pressable, Text, View } from "react-native";
import { AthleteName } from "../../athletes/AthleteCard";
import { AppTextInput as TextInput } from "../../components/AppTextInput";
import { StatusBadge } from "../../components/StatusBadge";
import { UiStatePanel } from "../../components/UiStatePanel";
import { TRADE_STATUS_COLOR, TRADE_STATUS_LABEL } from "../../market/marketLabels";
import { marketUiStyles as styles } from "../../market/marketUiStyles";
import type { useTradeFlow } from "../../market/useTradeFlow";

type TradeTab = "all" | "received" | "sent" | "done";
const OPEN_STATUSES = new Set(["proposed", "countered", "accepted", "pending_approval"]);

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
}: {
  trade: ReturnType<typeof useTradeFlow>;
  selfTeamId: string | undefined;
  teams: FantasyTeamSummary[];
  occupancy: RosterOccupancyEntry[];
  athleteNameById: Map<string, string>;
  ownedSlots: FantasyRosterSlot[];
  canManageMarket: boolean;
}) {
  const [tab, setTab] = useState<TradeTab>("all");
  const [counteringProposalId, setCounteringProposalId] = useState<string | null>(null);
  const [counterOfferedAthleteIds, setCounterOfferedAthleteIds] = useState<string[]>([]);
  const [counterRequestedAthleteIds, setCounterRequestedAthleteIds] = useState<string[]>([]);
  const [counterOfferedCredits, setCounterOfferedCredits] = useState("0");
  const [counterRequestedCredits, setCounterRequestedCredits] = useState("0");
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
    setCounterOfferedCredits("0");
    setCounterRequestedCredits("0");
    setCounterExpiresAt("");
  }

  function handleCounterSubmit(proposalId: string) {
    if (!counterExpiresAt.trim()) {
      return;
    }
    const parsed = new Date(counterExpiresAt.trim().replace(" ", "T"));
    if (Number.isNaN(parsed.getTime())) {
      return;
    }
    void trade
      .counterProposal(proposalId, {
        offeredAthleteIds: counterOfferedAthleteIds,
        requestedAthleteIds: counterRequestedAthleteIds,
        offeredCredits: Number(counterOfferedCredits) || 0,
        requestedCredits: Number(counterRequestedCredits) || 0,
        expiresAt: parsed.toISOString(),
      })
      .then(() => setCounteringProposalId(null));
  }

  const received = trade.proposals.filter(
    (row) => row.recipientTeamId === selfTeamId && OPEN_STATUSES.has(row.status),
  );
  const sent = trade.proposals.filter(
    (row) => row.proposerTeamId === selfTeamId && OPEN_STATUSES.has(row.status),
  );
  const done = trade.proposals.filter((row) => !OPEN_STATUSES.has(row.status));
  const visible =
    tab === "all" ? trade.proposals : tab === "received" ? received : tab === "sent" ? sent : done;
  const tabs: Array<{ id: TradeTab; label: string; count: number }> = [
    { id: "all", label: "Tutte", count: trade.proposals.length },
    { id: "received", label: "Ricevute", count: received.length },
    { id: "sent", label: "Inviate", count: sent.length },
    { id: "done", label: "Concluse", count: done.length },
  ];

  return (
    <View style={{ gap: 12 }} testID="wireframe-region-market-trade">
      <View style={styles.pillRow} testID="market-trade-tabs">
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
      </View>

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
                style={[styles.proposalCard, isRecipient && proposal.status === "proposed" && styles.proposalCardMine]}
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
                  <View style={styles.rowActions}>
                    <Pressable
                      style={[styles.button, pending && styles.disabled]}
                      disabled={pending}
                      onPress={() => void trade.acceptProposal(proposal.id)}
                      testID={`market-trade-accept-${proposal.id}`}
                    >
                      <Text style={styles.buttonLabel}>Accetta</Text>
                    </Pressable>
                    <Pressable
                      style={[styles.secondaryButton, pending && styles.disabled]}
                      disabled={pending}
                      onPress={() => void trade.rejectProposal(proposal.id)}
                      testID={`market-trade-reject-${proposal.id}`}
                    >
                      <Text style={styles.secondaryButtonLabel}>Rifiuta</Text>
                    </Pressable>
                    <Pressable
                      style={[
                        styles.secondaryButton,
                        (pending || ownedSlots.length === 0) && styles.disabled,
                      ]}
                      disabled={pending || ownedSlots.length === 0}
                      onPress={() => startCounter(proposal.id)}
                      testID={`market-trade-counter-start-${proposal.id}`}
                    >
                      <Text style={styles.secondaryButtonLabel}>Controproponi</Text>
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
                    <Text style={styles.fieldLabel}>Giocatori offerti nella controproposta</Text>
                    {ownedSlots.map((slot) => {
                      const checked = counterOfferedAthleteIds.includes(slot.athleteId as string);
                      return (
                        <Pressable
                          key={slot.id}
                          style={styles.optionRow}
                          onPress={() =>
                            setCounterOfferedAthleteIds((prev) =>
                              toggleId(prev, slot.athleteId as string),
                            )
                          }
                        >
                          <AthleteName athleteId={slot.athleteId} style={styles.optionLabel}>
                            {slot.athleteName ?? "Giocatore"}
                          </AthleteName>
                          <Text style={styles.meta}>{checked ? "☑" : "☐"}</Text>
                        </Pressable>
                      );
                    })}

                    <Text style={styles.fieldLabel}>Giocatori richiesti nella controproposta</Text>
                    {occupancy
                      .filter((entry) => entry.fantasyTeamId === proposal.proposerTeamId)
                      .map((entry) => {
                        const checked = counterRequestedAthleteIds.includes(entry.athleteId);
                        return (
                          <Pressable
                            key={entry.athleteId}
                            style={styles.optionRow}
                            onPress={() =>
                              setCounterRequestedAthleteIds((prev) => toggleId(prev, entry.athleteId))
                            }
                          >
                            <AthleteName athleteId={entry.athleteId} style={styles.optionLabel}>
                              {entry.athleteName ?? athleteNameById.get(entry.athleteId) ?? "Giocatore"}
                            </AthleteName>
                            <Text style={styles.meta}>{checked ? "☑" : "☐"}</Text>
                          </Pressable>
                        );
                      })}

                    <Text style={styles.fieldLabel}>Crediti offerti</Text>
                    <TextInput
                      style={styles.input}
                      value={counterOfferedCredits}
                      onChangeText={setCounterOfferedCredits}
                      keyboardType="numeric"
                    />
                    <Text style={styles.fieldLabel}>Crediti richiesti</Text>
                    <TextInput
                      style={styles.input}
                      value={counterRequestedCredits}
                      onChangeText={setCounterRequestedCredits}
                      keyboardType="numeric"
                    />
                    <Text style={styles.fieldLabel}>Scadenza (AAAA-MM-GG HH:MM)</Text>
                    <TextInput
                      style={styles.input}
                      value={counterExpiresAt}
                      onChangeText={setCounterExpiresAt}
                      placeholder="2026-09-01 00:00"
                      autoCapitalize="none"
                      autoCorrect={false}
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
