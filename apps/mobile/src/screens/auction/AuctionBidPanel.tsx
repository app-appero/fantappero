import type { ReactNode } from "react";
import { Pressable, Text, View } from "react-native";
import type { AthleteMarketFields, LeagueListoneEntry } from "@fantappero/contracts";
import { formatRomeDateTime } from "../../utils/romeTime";
import { AthleteMarketTags } from "../../market/AthleteMarketTags";
import { AthleteChooser } from "../../components/AthleteChooser";
import { AppTextInput as TextInput } from "../../components/AppTextInput";
import { OptionPicker, type OptionPickerOption } from "../../components/OptionPicker";
import { StatusBadge } from "../../components/StatusBadge";
import { UiStatePanel } from "../../components/UiStatePanel";
import { AthleteName } from "../../athletes/AthleteCard";
import { BID_STATUS_LABEL } from "../../market/marketLabels";
import { marketUiStyles as styles } from "../../market/marketUiStyles";
import type { MarketSessionFlow } from "../../market/useMarketSessionFlow";
import { theme } from "@fantappero/ui/theme";

const { colors } = theme;

/** Closed-envelope bid form + "my bids" table, shared shape between Asta (EP08-01/02) and Svincolati (EP08-03). */
export function AuctionBidPanel({
  flow,
  balance,
  playerOptions,
  chooserEntries,
  ownedAthleteIds,
  bidAthleteId,
  onBidAthleteIdChange,
  bidAmount,
  onBidAmountChange,
  onSubmit,
  athleteNameById,
  notOpenMessage = "Le offerte si possono inviare solo mentre la sessione è aperta.",
  statusMessage = "Asta a buste chiusa — offerta visibile solo a te fino alla chiusura.",
  testIdPrefix = "auction",
  extraField,
  marketOpen = true,
  closedMessage = null,
  closedTitle = "Mercato chiuso",
  selectedAthlete = null,
  prefillHint = null,
}: {
  flow: MarketSessionFlow;
  balance: number | null;
  playerOptions: readonly OptionPickerOption[];
  /** Se presenti, il giocatore si sceglie dall'elenco dei soli disponibili (per ruolo, a pagine). */
  chooserEntries?: LeagueListoneEntry[];
  ownedAthleteIds?: Set<string>;
  bidAthleteId: string;
  onBidAthleteIdChange: (value: string) => void;
  bidAmount: string;
  onBidAmountChange: (value: string) => void;
  onSubmit: () => void;
  athleteNameById: Map<string, string>;
  notOpenMessage?: string;
  statusMessage?: string;
  testIdPrefix?: string;
  extraField?: ReactNode;
  marketOpen?: boolean;
  /** Motivo del mercato fermo, se diverso dall'interruttore (es. lega non al completo, 20/11). */
  closedMessage?: string | null;
  /** Titolo del mercato fermo: «Mercato fermo: turno in corso» a turno in corso (21/11). */
  closedTitle?: string;
  /** Calciatore scelto: Valore e media accanto all'offerta (1.3). */
  selectedAthlete?: (AthleteMarketFields & { canonicalName: string }) | null;
  /**
   * Perché l'offerta parte da quel prezzo: «Proposta in base al Valore…» o
   * «Valore 58: hai solo 40 crediti» (Rosario, 21/11).
   */
  prefillHint?: string | null;
}) {
  const sessionOpen = marketOpen && flow.currentSession?.status === "open";

  return (
    <View style={styles.section} testID={`wireframe-region-${testIdPrefix}-bid`}>
      <Text style={styles.sectionTitle}>Nuova offerta</Text>

      {!sessionOpen ? (
        <UiStatePanel
          state="empty"
          title={!marketOpen ? closedTitle : "Asta non aperta"}
          message={
            !marketOpen
              ? (closedMessage ??
                "L'amministratore ha chiuso il mercato. Restano disponibili solo gli scambi.")
              : flow.currentSession?.status === "scheduled"
                ? `La sessione è programmata: si apre ${formatRomeDateTime(flow.currentSession.opensAt)} e chiude ${formatRomeDateTime(flow.currentSession.closesAt)}.`
                : notOpenMessage
          }
          testID={`${testIdPrefix}-bid-not-open`}
        />
      ) : (
        <View style={styles.field} testID={`${testIdPrefix}-bid-panel`}>
          <Text style={styles.meta}>Budget residuo: {balance !== null ? `${balance} crediti` : "—"}</Text>
          {chooserEntries && ownedAthleteIds ? (
            <View style={{ gap: 6 }}>
              <Text style={styles.fieldLabel}>Giocatore</Text>
              <AthleteChooser
                entries={chooserEntries}
                ownedAthleteIds={ownedAthleteIds}
                selected={bidAthleteId ? [bidAthleteId] : []}
                onToggle={(id) => onBidAthleteIdChange(id === bidAthleteId ? "" : id)}
                single
                testID={`${testIdPrefix}-bid-player`}
              />
            </View>
          ) : (
            <OptionPicker
              label="Giocatore"
              options={playerOptions}
              value={bidAthleteId}
              onChange={onBidAthleteIdChange}
              placeholder="Scegli un giocatore…"
              searchable
              testID={`${testIdPrefix}-bid-player`}
            />
          )}
          {extraField}
          <Text style={styles.fieldLabel}>Offerta (crediti)</Text>
          {selectedAthlete ? (
            <View testID={`${testIdPrefix}-bid-selected`}>
              <Text style={styles.meta} numberOfLines={1}>
                {selectedAthlete.canonicalName}
              </Text>
              <AthleteMarketTags fields={selectedAthlete} testID={`${testIdPrefix}-bid-selected-tags`} />
            </View>
          ) : null}
          <TextInput
            style={styles.input}
            value={bidAmount}
            onChangeText={onBidAmountChange}
            keyboardType="numeric"
            placeholder="Es. 45"
            testID={`${testIdPrefix}-bid-amount`}
          />
          {prefillHint ? (
            <Text style={[styles.meta, { color: colors.warning }]} testID={`${testIdPrefix}-bid-prefill-hint`}>
              {prefillHint}
            </Text>
          ) : null}
          <Text style={styles.meta}>{statusMessage}</Text>
          {flow.bidError ? (
            <Text style={styles.error} testID={`${testIdPrefix}-bid-error`}>
              {flow.bidError}
            </Text>
          ) : null}
          <Pressable
            style={[styles.button, flow.bidSubmitting && styles.disabled]}
            disabled={flow.bidSubmitting}
            onPress={onSubmit}
            testID={`${testIdPrefix}-bid-submit`}
          >
            <Text style={styles.buttonLabel}>
              {flow.bidSubmitting ? "Invio…" : "Invia offerta"}
            </Text>
          </Pressable>
        </View>
      )}

      {flow.bidSuccess ? (
        <UiStatePanel
          state="success"
          title="Fatto"
          message={flow.bidSuccess}
          testID={`${testIdPrefix}-bid-success`}
        />
      ) : null}

      {flow.myBids.length > 0 ? (
        <View testID={`${testIdPrefix}-my-bids-table`}>
          {flow.myBids.map((bid) => (
            <View key={bid.id} style={styles.tableRow}>
              {/* Più largo dei crediti: ci stanno anche Valore e media (1.3). */}
              <View style={{ flex: 2, minWidth: 0 }}>
                <AthleteName athleteId={bid.athleteId} style={styles.tableCell} numberOfLines={2}>
                  {athleteNameById.get(bid.athleteId) ?? bid.athleteName}
                </AthleteName>
                <AthleteMarketTags fields={bid} testID={`${testIdPrefix}-my-bid-tags-${bid.athleteId}`} />
              </View>
              <Text style={styles.tableCell}>{bid.amountCredits} crediti</Text>
              <StatusBadge
                label={BID_STATUS_LABEL[bid.status]}
                color={bid.status === "submitted" ? colors.success : colors.backgroundElevated}
                textColor={bid.status === "submitted" ? colors.accentContrast : colors.foreground}
              />
              {bid.status === "submitted" ? (
                <Pressable
                  style={styles.secondaryButton}
                  onPress={() => void flow.withdrawBid(bid.athleteId)}
                  testID={`${testIdPrefix}-bid-withdraw-${bid.athleteId}`}
                >
                  <Text style={styles.secondaryButtonLabel}>Ritira</Text>
                </Pressable>
              ) : null}
            </View>
          ))}
        </View>
      ) : null}
    </View>
  );
}
