import type {
  RosterOwnershipHistory,
  RosterTurnSnapshotDetail,
  RosterTurnSnapshotSummary,
} from "@fantappero/contracts";
import { theme } from "@fantappero/ui/theme";
import { Pressable, Text, TextInput, View } from "react-native";
import { UiStatePanel } from "../../components/UiStatePanel";
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
}) {
  return (
    <View testID="roster-history">
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
            <Text key={row.id} style={styles.meta}>
              {row.athleteName ?? row.athleteId} · slot {row.slotIndex + 1} ·{" "}
              {row.purchaseCredits} cr · {row.releasedAt ? "chiuso" : "in rosa"} · {row.source}
            </Text>
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
              <Text
                key={`${entry.fantasyTeamId}-${entry.slotIndex}-${entry.athleteId}`}
                style={styles.meta}
              >
                {entry.teamName}: {entry.athleteName ?? entry.athleteId} ({entry.role ?? "—"})
              </Text>
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
