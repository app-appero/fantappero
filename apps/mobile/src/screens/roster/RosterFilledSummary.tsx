import type { FantasyRole, FantasyTeam } from "@fantappero/contracts";
import { Pressable, Text, View } from "react-native";
import {
  compositionStatusLabel,
  ROLE_SECTION_ORDER,
  ROLE_SECTION_TITLE,
  roleBadgeColors,
} from "./rosterHelpers";
import { rosterStyles as styles } from "./rosterStyles";

type RosterSlot = FantasyTeam["slots"][number];

export function RosterFilledSummary({
  viewedTeam,
  filledByRole,
  canEdit,
  adminBusy,
  onReleaseAthlete,
}: {
  viewedTeam: FantasyTeam;
  filledByRole: Record<FantasyRole | "unknown", RosterSlot[]>;
  canEdit: boolean;
  adminBusy: boolean;
  onReleaseAthlete: (athleteId: string) => void | Promise<void>;
}) {
  return (
    <View testID="roster-success">
      <Text style={styles.summary} testID="roster-summary">
        {viewedTeam.name}: {viewedTeam.filledSlots}/{viewedTeam.rosterSize} giocatori
      </Text>
      {viewedTeam.composition ? (
        <View testID="roster-composition" style={styles.compositionBox}>
          <Text style={styles.meta}>
            Composizione: {compositionStatusLabel(viewedTeam.composition.status)}
          </Text>
          <Text style={styles.meta} testID="roster-composition-counts">
            {viewedTeam.composition.counts.P}/{viewedTeam.composition.limits.goalkeepers}P ·{" "}
            {viewedTeam.composition.counts.D}/{viewedTeam.composition.limits.defenders}D ·{" "}
            {viewedTeam.composition.counts.C}/{viewedTeam.composition.limits.midfielders}C ·{" "}
            {viewedTeam.composition.counts.A}/{viewedTeam.composition.limits.forwards}A ·{" "}
            {viewedTeam.composition.competitionCount} campionati
          </Text>
          {viewedTeam.composition.issues.map((issue) => (
            <Text key={`${issue.code}-${issue.message}`} style={styles.errorText}>
              {issue.message}
            </Text>
          ))}
        </View>
      ) : null}
      <View testID="roster-filled-table" style={styles.roleTables}>
        {ROLE_SECTION_ORDER.map((role) => {
          const slots = filledByRole[role];
          const limit =
            viewedTeam.composition?.limits == null
              ? null
              : role === "P"
                ? viewedTeam.composition.limits.goalkeepers
                : role === "D"
                  ? viewedTeam.composition.limits.defenders
                  : role === "C"
                    ? viewedTeam.composition.limits.midfielders
                    : viewedTeam.composition.limits.forwards;
          const roleColors = roleBadgeColors(role);
          return (
            <View key={role} style={styles.roleSection} testID={`roster-filled-table-${role}`}>
              <View style={styles.roleSectionHeader}>
                <View style={[styles.roleBadge, roleColors]}>
                  <Text style={[styles.roleBadgeText, { color: roleColors.color }]}>{role}</Text>
                </View>
                <Text style={styles.roleSectionTitle}>{ROLE_SECTION_TITLE[role]}</Text>
                <Text style={styles.roleSectionCount}>
                  {slots.length}
                  {limit != null ? `/${limit}` : ""}
                </Text>
              </View>
              {slots.length === 0 ? (
                <Text style={styles.meta}>Nessun giocatore in questo ruolo.</Text>
              ) : (
                slots.map((slot) => (
                  <View key={slot.id} style={styles.card}>
                    <Text style={styles.cardTitle}>{slot.athleteName ?? "Calciatore"}</Text>
                    <Text style={styles.meta}>
                      Club: {slot.clubName ?? "—"} · Crediti: {slot.purchaseCredits ?? "—"} · Slot{" "}
                      {slot.slotIndex + 1}
                    </Text>
                    {canEdit && slot.athleteId ? (
                      <Pressable
                        style={[styles.button, adminBusy && styles.disabled]}
                        disabled={adminBusy}
                        testID={`roster-admin-release-${slot.athleteId}`}
                        onPress={() => void onReleaseAthlete(slot.athleteId!)}
                      >
                        <Text style={styles.buttonLabel}>Rimuovi</Text>
                      </Pressable>
                    ) : null}
                  </View>
                ))
              )}
            </View>
          );
        })}
        {filledByRole.unknown.length > 0 ? (
          <View style={styles.roleSection} testID="roster-filled-table-unknown">
            <View style={styles.roleSectionHeader}>
              <Text style={styles.roleSectionTitle}>Senza ruolo</Text>
              <Text style={styles.roleSectionCount}>{filledByRole.unknown.length}</Text>
            </View>
            {filledByRole.unknown.map((slot) => (
              <View key={slot.id} style={styles.card}>
                <Text style={styles.cardTitle}>{slot.athleteName ?? "Calciatore"}</Text>
                <Text style={styles.meta}>
                  Club: {slot.clubName ?? "—"} · Crediti: {slot.purchaseCredits ?? "—"} · Slot{" "}
                  {slot.slotIndex + 1}
                </Text>
                {canEdit && slot.athleteId ? (
                  <Pressable
                    style={[styles.button, adminBusy && styles.disabled]}
                    disabled={adminBusy}
                    testID={`roster-admin-release-${slot.athleteId}`}
                    onPress={() => void onReleaseAthlete(slot.athleteId!)}
                  >
                    <Text style={styles.buttonLabel}>Rimuovi</Text>
                  </Pressable>
                ) : null}
              </View>
            ))}
          </View>
        ) : null}
      </View>
    </View>
  );
}
