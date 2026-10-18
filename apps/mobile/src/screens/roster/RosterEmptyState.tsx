import type { FantasyRole, FantasyTeam } from "@fantappero/contracts";
import { Pressable, Text, View } from "react-native";
import { ROLE_SECTION_ORDER, roleBadgeColors } from "./rosterHelpers";
import { rosterStyles as styles } from "./rosterStyles";

export function RosterEmptyState({
  viewedTeam,
  onGoAuction,
}: {
  viewedTeam: FantasyTeam;
  onGoAuction?: () => void;
}) {
  const limits = viewedTeam.composition?.limits;
  const need = (role: FantasyRole): number =>
    !limits ? 0 : role === "P" ? limits.goalkeepers : role === "D" ? limits.defenders : role === "C" ? limits.midfielders : limits.forwards;
  return (
    <View testID="roster-empty" style={{ gap: 12 }}>
      {limits ? (
        <View style={styles.tiles}>
          {ROLE_SECTION_ORDER.map((role) => {
            const dot = roleBadgeColors(role);
            return (
              <View key={role} style={[styles.tile, styles.tileMissing]}>
                <View style={[styles.playerDot, { backgroundColor: dot.backgroundColor, width: 26, height: 26, borderRadius: 13 }]}>
                  <Text style={[styles.roleBadgeText, { color: dot.color }]}>{role}</Text>
                </View>
                <Text style={styles.tileCount}>0/{need(role)}</Text>
                <View style={styles.tileBar} />
              </View>
            );
          })}
        </View>
      ) : null}
      <View style={styles.emptyCard}>
        <Text style={styles.emptyTitle}>La tua rosa è vuota</Text>
        <Text style={styles.emptyText}>
          Costruiscila all'asta o aspetta che l'amministratore importi le rose.
          {limits
            ? ` Servono ${viewedTeam.rosterSize} giocatori: ${limits.goalkeepers} P · ${limits.defenders} D · ${limits.midfielders} C · ${limits.forwards} A.`
            : ""}
        </Text>
        {onGoAuction ? (
          <Pressable style={[styles.button, { alignSelf: "stretch" }]} onPress={onGoAuction} testID="roster-empty-auction">
            <Text style={styles.buttonLabel}>Vai all'asta</Text>
          </Pressable>
        ) : null}
      </View>
      <Text style={styles.meta} testID="roster-empty-summary">
        {viewedTeam.name}: 0/{viewedTeam.rosterSize} slot occupati
      </Text>
    </View>
  );
}
