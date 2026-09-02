import type { ReactNode } from "react";
import { Pressable, Text, TextInput, View } from "react-native";
import { OptionPicker, type OptionPickerOption } from "../../components/OptionPicker";
import { StatusBadge } from "../../components/StatusBadge";
import { UiStatePanel } from "../../components/UiStatePanel";
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
}: {
  flow: MarketSessionFlow;
  balance: number | null;
  playerOptions: readonly OptionPickerOption[];
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
}) {
  const sessionOpen = flow.currentSession?.status === "open";

  return (
    <View style={styles.section} testID={`wireframe-region-${testIdPrefix}-bid`}>
      <Text style={styles.sectionTitle}>Nuova offerta</Text>

      {!sessionOpen ? (
        <UiStatePanel
          state="empty"
          title="Asta non aperta"
          message={notOpenMessage}
          testID={`${testIdPrefix}-bid-not-open`}
        />
      ) : (
        <View style={styles.field} testID={`${testIdPrefix}-bid-panel`}>
          <Text style={styles.meta}>Budget residuo: {balance !== null ? `${balance} crediti` : "—"}</Text>
          <OptionPicker
            label="Giocatore"
            options={playerOptions}
            value={bidAthleteId}
            onChange={onBidAthleteIdChange}
            placeholder="Scegli un giocatore…"
            searchable
            testID={`${testIdPrefix}-bid-player`}
          />
          {extraField}
          <Text style={styles.fieldLabel}>Offerta (crediti)</Text>
          <TextInput
            style={styles.input}
            value={bidAmount}
            onChangeText={onBidAmountChange}
            keyboardType="numeric"
            placeholder="Es. 45"
            testID={`${testIdPrefix}-bid-amount`}
          />
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
              <Text style={styles.tableCell}>{athleteNameById.get(bid.athleteId) ?? bid.athleteName}</Text>
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
