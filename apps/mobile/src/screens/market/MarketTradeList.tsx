import type { FantasyRosterSlot, FantasyTeamSummary, RosterOccupancyEntry } from "@fantappero/contracts";
import { useState } from "react";
import { Pressable, Text, TextInput, View } from "react-native";
import { StatusBadge } from "../../components/StatusBadge";
import { UiStatePanel } from "../../components/UiStatePanel";
import { TRADE_STATUS_COLOR, TRADE_STATUS_LABEL } from "../../market/marketLabels";
import { marketUiStyles as styles } from "../../market/marketUiStyles";
import type { useTradeFlow } from "../../market/useTradeFlow";

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

  return (
    <View style={styles.section} testID="wireframe-region-market-trade">
      <Text style={styles.sectionTitle}>Proposte di scambio</Text>

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

      {!trade.loading && !trade.loadError && trade.proposals.length === 0 ? (
        <UiStatePanel
          state="empty"
          title="Nessuna proposta"
          message="Non ci sono proposte di scambio inviate o ricevute."
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

      {!trade.loading && !trade.loadError && trade.proposals.length > 0 ? (
        <View testID="market-trade-list">
          {trade.proposals.map((proposal) => {
            const isProposer = proposal.proposerTeamId === selfTeamId;
            const isRecipient = proposal.recipientTeamId === selfTeamId;
            const pending = trade.actionPendingId === proposal.id;
            const statusColor = TRADE_STATUS_COLOR[proposal.status];
            return (
              <View
                key={proposal.id}
                style={styles.listRow}
                testID={`market-trade-proposal-${proposal.id}`}
              >
                <View style={styles.rowActions}>
                  <Text style={styles.meta}>
                    {teamNameFor(proposal.proposerTeamId)} → {teamNameFor(proposal.recipientTeamId)}
                  </Text>
                  <StatusBadge
                    label={TRADE_STATUS_LABEL[proposal.status]}
                    color={statusColor.background}
                    textColor={statusColor.text}
                  />
                </View>
                <Text style={styles.meta}>
                  Offerti: {proposal.offeredAthletes.map((a) => a.name).join(", ") || "—"}
                  {proposal.offeredCredits > 0 ? ` + ${proposal.offeredCredits} crediti` : ""}
                </Text>
                <Text style={styles.meta}>
                  Richiesti: {proposal.requestedAthletes.map((a) => a.name).join(", ") || "—"}
                  {proposal.requestedCredits > 0 ? ` + ${proposal.requestedCredits} crediti` : ""}
                </Text>

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
                      style={[styles.secondaryButton, pending && styles.disabled]}
                      disabled={pending}
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
                          <Text style={styles.optionLabel}>{slot.athleteName ?? "Giocatore"}</Text>
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
                            <Text style={styles.optionLabel}>
                              {entry.athleteName ?? athleteNameById.get(entry.athleteId) ?? "Giocatore"}
                            </Text>
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
