import type { CreditAccount, FantasyTeamSummary } from "@fantappero/contracts";
import { theme } from "@fantappero/ui/theme";
import { useState } from "react";
import { Modal, Pressable, ScrollView, Text, View } from "react-native";
import { HScroll } from "../../components/HScroll";
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
  teamName,
  filledSlots,
  rosterSize,
  spent,
  leagueName,
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
  teamName?: string | null;
  filledSlots?: number | null;
  rosterSize?: number | null;
  /** Crediti spesi per i giocatori in rosa (somma dei prezzi di acquisto). */
  spent?: number | null;
  leagueName?: string | null;
}) {
  const [open, setOpen] = useState(false);
  const [teamsOpen, setTeamsOpen] = useState(false);
  const canSwitch = isAdmin && leagueTeams.length > 1;

  return (
    <View style={styles.credits} testID="roster-credits">
      <View style={styles.heroCard}>
        <View style={styles.heroTop}>
          <View style={styles.heroAvatar}>
            <Text style={styles.heroAvatarLabel}>{(teamName ?? "?").slice(0, 2).toUpperCase()}</Text>
          </View>
          <View style={{ flex: 1, minWidth: 0 }}>
            <Text style={styles.heroName} numberOfLines={2}>
              {teamName ?? "La tua squadra"}
            </Text>
            {leagueName ? (
              <Text style={styles.heroSub} numberOfLines={1}>
                {leagueName}
              </Text>
            ) : null}
          </View>
        </View>
        <View style={styles.heroRow}>
          <View>
            <Text style={styles.heroLabel}>Crediti residui</Text>
            <Text style={styles.heroBalance} testID="roster-credits-balance" numberOfLines={1}>
              {credits?.balance ?? "—"}
            </Text>
          </View>
          {filledSlots != null && rosterSize != null ? (
            <View>
              <Text style={[styles.heroLabel, { textAlign: "right" }]}>Giocatori</Text>
              <Text style={styles.heroSlots}>
                {filledSlots}
                <Text style={styles.heroSlotsNeed}>/{rosterSize}</Text>
              </Text>
            </View>
          ) : null}
        </View>
        {spent != null && credits ? (
          <>
            <View style={styles.heroBar}>
              <View
                style={[
                  styles.heroBarFill,
                  { width: `${Math.min(100, Math.round((spent / Math.max(1, spent + credits.balance)) * 100))}%` as `${number}%` },
                ]}
              />
            </View>
            <View style={styles.heroFoot}>
              <Text style={styles.heroFootLabel}>
                Spesi {spent} su {spent + credits.balance}
              </Text>
              <Text style={styles.heroFootLabel}>
                {Math.round((spent / Math.max(1, spent + credits.balance)) * 100)}%
              </Text>
            </View>
          </>
        ) : null}
        {canSwitch || isAdmin ? (
          <HScroll>
            {canSwitch ? (
              <Pressable style={styles.creditsButton} onPress={() => setTeamsOpen(true)} testID="roster-admin-team">
                <Text style={styles.creditsButtonLabel}>Cambia squadra</Text>
              </Pressable>
            ) : null}
            {isAdmin ? (
              <Pressable style={styles.creditsButton} onPress={() => setOpen(true)} testID="roster-admin-credits">
                <Text style={styles.creditsButtonLabel}>Aggiusta crediti</Text>
              </Pressable>
            ) : null}
          </HScroll>
        ) : null}
      </View>
      <Modal visible={teamsOpen} transparent animationType="slide" onRequestClose={() => setTeamsOpen(false)}>
        <Pressable style={styles.adjustBackdrop} onPress={() => setTeamsOpen(false)}>
          <Pressable style={styles.adjustSheet} onPress={() => undefined} testID="roster-admin-team-sheet">
            <Text style={styles.blockTitle}>Squadra</Text>
            <ScrollView style={{ maxHeight: 420 }} contentContainerStyle={{ gap: 6 }}>
              {leagueTeams.map((row) => {
                const selected = row.id === adminTeamId;
                return (
                  <Pressable
                    key={row.id}
                    style={[styles.moveRow, selected && { borderColor: theme.colors.brand }]}
                    disabled={adminBusy || adjusting}
                    onPress={() => {
                      onSelectAdminTeam(row.id);
                      setTeamsOpen(false);
                    }}
                  >
                    <Text style={[styles.moveTitle, { flex: 1 }]} numberOfLines={1}>
                      {row.name}
                    </Text>
                    <Text style={styles.moveDate}>{`${row.filledSlots}/${row.rosterSize}`}</Text>
                    {selected ? <Text style={styles.moveTitle}>✓</Text> : null}
                  </Pressable>
                );
              })}
            </ScrollView>
          </Pressable>
        </Pressable>
      </Modal>
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
