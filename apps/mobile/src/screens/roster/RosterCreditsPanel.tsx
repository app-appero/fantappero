import type { CreditAccount, FantasyTeamSummary } from "@fantappero/contracts";
import { Pressable, Text, View } from "react-native";
import { AppTextInput as TextInput } from "../../components/AppTextInput";
import { rosterStyles as styles } from "./rosterStyles";

export function RosterCreditsPanel({
  isAdmin,
  leagueTeams,
  adminTeamId,
  onSelectAdminTeam,
  adminBusy,
  adjusting,
  hasAdjustTarget,
  credits,
  adjustAmount,
  onAdjustAmountChange,
  adjustNote,
  onAdjustNoteChange,
  onAdminAdjust,
  adjustMessage,
  adjustError,
}: {
  isAdmin: boolean;
  leagueTeams: FantasyTeamSummary[];
  adminTeamId: string;
  onSelectAdminTeam: (teamId: string) => void;
  adminBusy: boolean;
  adjusting: boolean;
  hasAdjustTarget: boolean;
  credits: CreditAccount | null;
  adjustAmount: string;
  onAdjustAmountChange: (value: string) => void;
  adjustNote: string;
  onAdjustNoteChange: (value: string) => void;
  onAdminAdjust: () => void | Promise<void>;
  adjustMessage: string | null;
  adjustError: string | null;
}) {
  return (
    <View style={styles.credits} testID="roster-credits">
      {isAdmin && leagueTeams.length > 0 ? (
        <>
          <Text style={styles.summary}>Squadra target</Text>
          <View style={styles.chipRow} testID="roster-admin-team">
            {leagueTeams.map((row) => {
              const selected = row.id === adminTeamId;
              return (
                <Pressable
                  key={row.id}
                  style={[styles.chip, selected && styles.chipSelected]}
                  disabled={adminBusy || adjusting}
                  onPress={() => onSelectAdminTeam(row.id)}
                >
                  <Text style={[styles.chipLabel, selected && styles.chipLabelSelected]}>
                    {row.name} ({row.filledSlots}/{row.rosterSize})
                  </Text>
                </Pressable>
              );
            })}
          </View>
        </>
      ) : null}
      <Text style={styles.summary} testID="roster-credits-balance">
        Crediti residui: {credits?.balance ?? "—"}
        {credits ? ` (v${credits.version})` : ""}
      </Text>
      {isAdmin ? (
        <View style={styles.inlineAdjust} testID="roster-admin-credits">
          <TextInput
            style={styles.input}
            value={adjustAmount}
            onChangeText={onAdjustAmountChange}
            keyboardType="numeric"
            placeholder="Importo"
            testID="roster-adjust-amount"
          />
          <TextInput
            style={styles.input}
            value={adjustNote}
            onChangeText={onAdjustNoteChange}
            placeholder="Nota"
            testID="roster-adjust-note"
          />
          <Pressable
            style={[styles.button, (adjusting || !hasAdjustTarget) && styles.disabled]}
            disabled={adjusting || !hasAdjustTarget}
            onPress={() => void onAdminAdjust()}
          >
            <Text style={styles.buttonLabel}>
              {adjusting ? "Registrazione…" : "Aggiusta crediti"}
            </Text>
          </Pressable>
          {adjustMessage ? (
            <Text style={styles.ok} testID="roster-adjust-ok">
              {adjustMessage}
            </Text>
          ) : null}
          {adjustError ? (
            <Text style={styles.error} testID="roster-adjust-error">
              {adjustError}
            </Text>
          ) : null}
        </View>
      ) : null}
    </View>
  );
}
