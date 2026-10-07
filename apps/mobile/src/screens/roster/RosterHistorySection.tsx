import type {
  CreditLedgerList,
  RosterOwnershipHistory,
  RosterTurnSnapshotDetail,
  RosterTurnSnapshotSummary,
} from "@fantappero/contracts";
import { theme } from "@fantappero/ui/theme";
import { Pressable, Text, View } from "react-native";
import { AppTextInput as TextInput } from "../../components/AppTextInput";
import { UiStatePanel } from "../../components/UiStatePanel";
import { AthleteName } from "../../athletes/AthleteCard";
import { formatLedgerEntry, LEDGER_PAGE_SIZE } from "./rosterHelpers";
import { rosterStyles as styles } from "./rosterStyles";

const { spacing } = theme;

export function RosterHistorySection({
  historyLoading,
  historyError,
  history,
  snapshots,
  snapshotDetail,
  snapshotRound,
  onSnapshotRoundChange,
  snapshotBusy,
  isAdmin,
  onCreateSnapshot,
  snapshotMessage,
  snapshotError,
  hasLedger,
  pagedLedgerEntries,
  ledgerEntriesCount,
  safeLedgerPage,
  ledgerPageCount,
  onLedgerPagePrev,
  onLedgerPageNext,
}: {
  historyLoading: boolean;
  historyError: string | null;
  history: RosterOwnershipHistory | null;
  snapshots: RosterTurnSnapshotSummary[];
  snapshotDetail: RosterTurnSnapshotDetail | null;
  snapshotRound: string;
  onSnapshotRoundChange: (value: string) => void;
  snapshotBusy: boolean;
  isAdmin: boolean;
  onCreateSnapshot: () => void | Promise<void>;
  snapshotMessage: string | null;
  snapshotError: string | null;
  hasLedger: boolean;
  pagedLedgerEntries: CreditLedgerList["entries"];
  ledgerEntriesCount: number;
  safeLedgerPage: number;
  ledgerPageCount: number;
  onLedgerPagePrev: () => void;
  onLedgerPageNext: () => void;
}) {
  return (
    <View testID="roster-history">
      <View style={{ marginBottom: spacing.md }}>
        <Text style={styles.summary}>Movimenti crediti</Text>
        {hasLedger ? (
          <View testID="roster-credits-ledger">
            {pagedLedgerEntries.map((entry) => (
              <Text key={entry.id} style={styles.meta}>
                {formatLedgerEntry(entry)}
              </Text>
            ))}
            {ledgerEntriesCount > LEDGER_PAGE_SIZE ? (
              <View style={styles.pagination}>
                <Pressable
                  style={[styles.ghostButton, safeLedgerPage <= 0 && styles.disabled]}
                  disabled={safeLedgerPage <= 0}
                  testID="roster-credits-ledger-prev"
                  onPress={onLedgerPagePrev}
                >
                  <Text style={styles.ghostButtonLabel}>Precedenti</Text>
                </Pressable>
                <Text style={styles.meta} testID="roster-credits-ledger-page">
                  {safeLedgerPage + 1}/{ledgerPageCount}
                </Text>
                <Pressable
                  style={[
                    styles.ghostButton,
                    safeLedgerPage >= ledgerPageCount - 1 && styles.disabled,
                  ]}
                  disabled={safeLedgerPage >= ledgerPageCount - 1}
                  testID="roster-credits-ledger-next"
                  onPress={onLedgerPageNext}
                >
                  <Text style={styles.ghostButtonLabel}>Successivi</Text>
                </Pressable>
              </View>
            ) : null}
          </View>
        ) : (
          <UiStatePanel
            state="empty"
            title="Nessun movimento"
            message="Il ledger crediti non contiene ancora movimenti."
            testID="roster-credits-empty"
          />
        )}
      </View>
      {historyLoading ? (
        <UiStatePanel
          state="loading"
          title="Caricamento storico"
          message="Recupero intervalli e snapshot…"
          testID="roster-history-loading"
        />
      ) : null}
      {!historyLoading && historyError ? (
        <UiStatePanel
          state="error"
          title="Storico non disponibile"
          message={historyError}
          testID="roster-history-error"
        />
      ) : null}
      {!historyLoading && !historyError && history && history.intervals.length === 0 ? (
        <UiStatePanel
          state="empty"
          title="Nessun possesso registrato"
          message="Gli intervalli compaiono dopo assegnazioni o rilasci."
          testID="roster-history-empty"
        />
      ) : null}
      {!historyLoading && !historyError && history && history.intervals.length > 0 ? (
        <View testID="roster-history-success">
          <Text style={styles.summary}>Intervalli di possesso</Text>
          {history.intervals.map((row) => (
            <View key={row.id} style={{ flexDirection: "row", flexWrap: "wrap" }}>
              <AthleteName athleteId={row.athleteId} style={styles.meta}>
                {row.athleteName ?? row.athleteId}
              </AthleteName>
              <Text style={styles.meta}>
                {" "}
                · slot {row.slotIndex + 1} · {row.purchaseCredits} cr · {row.releasedAt ? "chiuso" : "in rosa"} ·{" "}
                {row.source}
              </Text>
            </View>
          ))}
        </View>
      ) : null}
      <View style={{ marginTop: spacing.md }} testID="roster-snapshots">
        <Text style={styles.summary}>Snapshot per turno</Text>
        <TextInput
          style={styles.input}
          value={snapshotRound}
          onChangeText={onSnapshotRoundChange}
          keyboardType="numeric"
          placeholder="Numero turno"
          testID="roster-snapshot-round"
        />
        {isAdmin ? (
          <Pressable
            style={[styles.button, snapshotBusy && styles.disabled]}
            disabled={snapshotBusy}
            onPress={() => void onCreateSnapshot()}
            testID="roster-snapshot-create"
          >
            <Text style={styles.buttonLabel}>
              {snapshotBusy ? "Salvataggio…" : "Crea snapshot turno"}
            </Text>
          </Pressable>
        ) : null}
        {snapshotMessage ? (
          <Text style={styles.ok} testID="roster-snapshot-ok">
            {snapshotMessage}
          </Text>
        ) : null}
        {snapshotError ? (
          <Text style={styles.error} testID="roster-snapshot-error">
            {snapshotError}
          </Text>
        ) : null}
        {!snapshotDetail ? (
          <UiStatePanel
            state="empty"
            title="Nessuno snapshot"
            message="Crea uno snapshot per congelare la rosa di un turno."
            testID="roster-snapshot-empty"
          />
        ) : (
          <View testID="roster-snapshot-detail">
            <Text style={styles.meta}>
              Turno {snapshotDetail.roundNumber} · {snapshotDetail.entryCount} assegnazioni
            </Text>
            {snapshotDetail.entries.map((entry) => (
              <View
                key={`${entry.fantasyTeamId}-${entry.slotIndex}-${entry.athleteId}`}
                style={{ flexDirection: "row", flexWrap: "wrap" }}
              >
                <Text style={styles.meta}>{entry.teamName}: </Text>
                <AthleteName athleteId={entry.athleteId} style={styles.meta}>
                  {entry.athleteName ?? entry.athleteId}
                </AthleteName>
                <Text style={styles.meta}> ({entry.role ?? "—"})</Text>
              </View>
            ))}
            {snapshots.length > 0 ? (
              <Text style={styles.meta}>
                Snapshot disponibili: {snapshots.map((row) => row.roundNumber).join(", ")}
              </Text>
            ) : null}
          </View>
        )}
      </View>
    </View>
  );
}
