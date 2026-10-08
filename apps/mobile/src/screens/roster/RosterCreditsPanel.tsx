import type { CreditAccount, FantasyTeamSummary } from "@fantappero/contracts";
import { useState } from "react";
import { Modal, Pressable, ScrollView, Text, View } from "react-native";
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
  const [open, setOpen] = useState(false);

  return (
    <View style={styles.credits} testID="roster-credits">
      {isAdmin && leagueTeams.length > 0 ? (
        <ScrollView
          horizontal
          showsHorizontalScrollIndicator={false}
          contentContainerStyle={[styles.chipRow, styles.chipRowNowrap]}
          testID="roster-admin-team"
        >
          {leagueTeams.map((row) => {
            const selected = row.id === adminTeamId;
            return (
              <Pressable
                key={row.id}
                style={[styles.chip, selected && styles.chipSelected]}
                disabled={adminBusy || adjusting}
                onPress={() => onSelectAdminTeam(row.id)}
              >
                <Text style={[styles.chipLabel, selected && styles.chipLabelSelected]} numberOfLines={1}>
                  {row.name}
                </Text>
              </Pressable>
            );
          })}
        </ScrollView>
      ) : null}
      <View style={styles.creditsRow}>
        <Text style={styles.creditsBalance} testID="roster-credits-balance" numberOfLines={1}>
          Crediti residui: {credits?.balance ?? "—"}
        </Text>
        {isAdmin ? (
          <Pressable
            style={styles.creditsButton}
            onPress={() => setOpen(true)}
            testID="roster-admin-credits"
          >
            <Text style={styles.creditsButtonLabel}>Aggiusta crediti</Text>
          </Pressable>
        ) : null}
      </View>
      <Modal
        visible={open}
        transparent
        animationType="fade"
        onRequestClose={() => setOpen(false)}
      >
        <View style={styles.adjustBackdrop}>
          <Pressable style={styles.adjustBackdropTap} onPress={() => setOpen(false)} />
          <View style={styles.adjustSheet} testID="roster-adjust-sheet">
            <Text style={styles.cardTitle}>Aggiusta crediti</Text>
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
                {adjusting ? "Registrazione…" : "Registra"}
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
            <Pressable style={styles.creditsButton} onPress={() => setOpen(false)}>
              <Text style={styles.creditsButtonLabel}>Chiudi</Text>
            </Pressable>
          </View>
        </View>
      </Modal>
    </View>
  );
}
