import type { FantasyRosterSlot, MarketReleasePreview, MarketReleaseReason } from "@fantappero/contracts";
import { Pressable, Text, View } from "react-native";
import { OptionPicker, type OptionPickerOption } from "../../components/OptionPicker";
import { UiStatePanel } from "../../components/UiStatePanel";
import { RELEASE_REASON_OPTIONS } from "../../market/marketLabels";
import { marketUiStyles as styles } from "../../market/marketUiStyles";

/** Svincolo volontario con anteprima rimborso e conferma (EP08-04 / FR-MKT-02). */
export function MarketReleaseSection({
  ownedSlots,
  balance,
  slotOptions,
  selectedSlotIndex,
  onSelectedSlotIndexChange,
  reason,
  onReasonChange,
  onPreview,
  onApply,
  previewLoading,
  applying,
  preview,
  previewError,
  applyError,
  applySuccess,
}: {
  ownedSlots: FantasyRosterSlot[];
  balance: number | null;
  slotOptions: readonly OptionPickerOption[];
  selectedSlotIndex: string;
  onSelectedSlotIndexChange: (value: string) => void;
  reason: MarketReleaseReason;
  onReasonChange: (value: MarketReleaseReason) => void;
  onPreview: () => void;
  onApply: () => void;
  previewLoading: boolean;
  applying: boolean;
  preview: MarketReleasePreview | null;
  previewError: string | null;
  applyError: string | null;
  applySuccess: string | null;
}) {
  return (
    <View style={styles.section} testID="market-release-section">
      <Text style={styles.sectionTitle}>Svincolo volontario</Text>

      {ownedSlots.length === 0 ? (
        <UiStatePanel
          state="empty"
          title="Nessun giocatore da svincolare"
          message="La tua rosa non ha ancora giocatori assegnati."
          testID="wireframe-market-success"
        />
      ) : (
        <View style={styles.field} testID="wireframe-market-success">
          <Text style={styles.meta}>Budget residuo: {balance !== null ? `${balance} crediti` : "—"}</Text>
          <OptionPicker
            label="Giocatore da svincolare"
            options={slotOptions}
            value={selectedSlotIndex}
            onChange={onSelectedSlotIndexChange}
            placeholder="Scegli un giocatore…"
            testID="market-release-slot"
          />
          <OptionPicker
            label="Motivo"
            options={RELEASE_REASON_OPTIONS}
            value={reason}
            onChange={(value) => onReasonChange(value as MarketReleaseReason)}
            testID="market-release-reason"
          />

          <View style={styles.rowActions}>
            <Pressable
              style={[styles.secondaryButton, (selectedSlotIndex === "" || previewLoading) && styles.disabled]}
              disabled={selectedSlotIndex === "" || previewLoading}
              onPress={onPreview}
              testID="market-release-preview-submit"
            >
              <Text style={styles.secondaryButtonLabel}>{previewLoading ? "Calcolo…" : "Calcola rimborso"}</Text>
            </Pressable>
            <Pressable
              style={[styles.button, (!preview || applying) && styles.disabled]}
              disabled={!preview || applying}
              onPress={onApply}
              testID="market-release-apply-submit"
            >
              <Text style={styles.buttonLabel}>{applying ? "Conferma…" : "Conferma svincolo"}</Text>
            </Pressable>
          </View>

          {previewError ? (
            <UiStatePanel
              state="error"
              title="Anteprima non disponibile"
              message={previewError}
              testID="market-release-preview-error"
            />
          ) : null}

          {preview ? (
            <Text style={styles.meta} testID="market-release-preview">
              Rimborso stimato: {preview.refundCredits} crediti ({preview.refundPercent}% di{" "}
              {preview.purchaseCredits})
            </Text>
          ) : null}

          {applyError ? (
            <UiStatePanel
              state="error"
              title="Svincolo non riuscito"
              message={applyError}
              testID="market-release-apply-error"
            />
          ) : null}

          {applySuccess ? (
            <UiStatePanel
              state="success"
              title="Fatto"
              message={applySuccess}
              testID="market-release-apply-success"
            />
          ) : null}
        </View>
      )}
    </View>
  );
}
