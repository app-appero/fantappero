import { LOGIN_SHOWCASE_LEAGUES, LOGIN_SHOWCASE_PITCH, type ShowcaseRole } from "@fantappero/contracts";
import { theme } from "@fantappero/ui/theme";
import { StyleSheet, Text, View } from "react-native";

const { colors, spacing, radius } = theme;

const ROLE_COLOR: Record<ShowcaseRole, string> = { P: "#4ADE80", D: "#FFD23F", C: "#38BDF8", A: "#FF6B8A" };

/** Accesso: campo con top player di campionati diversi e una riga per campionato. */
export function LoginShowcase() {
  return (
    <View style={styles.wrap} testID="login-showcase">
      <Text style={styles.tagline}>5 campionati, una sola lega. I top player di tutta Europa.</Text>
      <View style={styles.pitch} accessibilityElementsHidden importantForAccessibility="no-hide-descendants">
        <View style={styles.pitchFrame} />
        <View style={styles.halfway} />
        {LOGIN_SHOWCASE_PITCH.map((p) => (
          <View key={p.name} style={[styles.slot, { left: `${p.x}%`, top: `${p.y}%` }]}>
            <View
              style={[
                styles.circle,
                { borderColor: ROLE_COLOR[p.role] },
                p.state === "final" ? styles.circleFinal : null,
                p.state === "live" ? styles.circleLive : null,
              ]}
            >
              <Text style={styles.initial}>{p.name.charAt(0)}</Text>
              <Text style={styles.flag}>{p.flag}</Text>
            </View>
            <Text style={styles.name} numberOfLines={1}>
              {p.name}
            </Text>
          </View>
        ))}
        <View style={styles.badges}>
          <View style={styles.goal}>
            <Text style={styles.goalLabel}>⚽ Gol!</Text>
          </View>
          <View style={styles.vote}>
            <Text style={styles.voteLabel}>8,0</Text>
          </View>
        </View>
      </View>
      <View style={styles.leagues}>
        {LOGIN_SHOWCASE_LEAGUES.map((league) => (
          <View key={league.name} style={styles.league}>
            <Text style={styles.leagueFlag}>{league.flag}</Text>
            <View style={styles.leagueBody}>
              <Text style={styles.leagueName}>{league.name}</Text>
              <View style={styles.pills}>
                {league.players.map((pl) => (
                  <View key={pl.name} style={styles.pill}>
                    <View style={[styles.pillRole, { backgroundColor: ROLE_COLOR[pl.role] }]}>
                      <Text style={styles.pillRoleLabel}>{pl.role}</Text>
                    </View>
                    <Text style={styles.pillName} numberOfLines={1}>
                      {pl.name}
                    </Text>
                  </View>
                ))}
              </View>
            </View>
          </View>
        ))}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { gap: spacing.sm, marginTop: spacing.sm },
  tagline: { color: colors.foregroundMuted, fontSize: 14 },
  pitch: {
    height: 168,
    borderRadius: 24,
    overflow: "hidden",
    backgroundColor: "#12795A",
    borderWidth: 1,
    borderColor: "rgba(255,255,255,0.18)",
  },
  pitchFrame: { position: "absolute", top: 6, left: 6, right: 6, bottom: 6, borderWidth: 2, borderColor: "rgba(255,255,255,0.28)", borderRadius: 8 },
  halfway: { position: "absolute", left: 6, right: 6, top: "50%", height: 2, backgroundColor: "rgba(255,255,255,0.28)" },
  slot: { position: "absolute", width: 64, marginLeft: -32, marginTop: -20, alignItems: "center", gap: 2 },
  circle: { width: 28, height: 28, borderRadius: 14, borderWidth: 3, backgroundColor: "#ffffff", alignItems: "center", justifyContent: "center" },
  circleFinal: { borderColor: "#ffffff", shadowColor: "#ffffff", shadowOpacity: 0.9, shadowRadius: 6, shadowOffset: { width: 0, height: 0 }, elevation: 4 },
  circleLive: { borderColor: "#4C86FF", shadowColor: "#4C86FF", shadowOpacity: 0.9, shadowRadius: 6, shadowOffset: { width: 0, height: 0 }, elevation: 4 },
  initial: { color: "#0A0F22", fontWeight: "800", fontStyle: "italic", fontSize: 12 },
  flag: { position: "absolute", right: -10, top: -8, fontSize: 11 },
  name: { color: "#ffffff", fontSize: 8, fontWeight: "600", backgroundColor: "rgba(8,12,30,0.8)", borderRadius: 999, paddingHorizontal: 6, overflow: "hidden" },
  badges: { position: "absolute", bottom: 8, left: 10, flexDirection: "row", gap: 6 },
  goal: { backgroundColor: "rgba(8,12,30,0.8)", borderRadius: 999, paddingHorizontal: 9, paddingVertical: 3 },
  goalLabel: { color: "#ffffff", fontSize: 10, fontWeight: "700" },
  vote: { backgroundColor: "#ffffff", borderRadius: 999, paddingHorizontal: 9, paddingVertical: 3 },
  voteLabel: { color: "#11162B", fontSize: 10, fontWeight: "800" },
  leagues: { gap: 7 },
  league: { flexDirection: "row", alignItems: "center", gap: 10, padding: 8, paddingHorizontal: 10, borderRadius: radius.lg, borderWidth: 1, borderColor: colors.border, backgroundColor: "rgba(24,30,60,0.75)" },
  leagueFlag: { fontSize: 20 },
  leagueBody: { flex: 1, minWidth: 0, gap: 4 },
  leagueName: { color: colors.foreground, fontWeight: "700", fontSize: 13 },
  pills: { flexDirection: "row", gap: 6 },
  pill: { flex: 1, minWidth: 0, flexDirection: "row", alignItems: "center", gap: 4, paddingVertical: 3, paddingLeft: 3, paddingRight: 6, borderRadius: 999, backgroundColor: "rgba(255,255,255,0.08)" },
  pillRole: { width: 17, height: 17, borderRadius: 9, alignItems: "center", justifyContent: "center" },
  pillRoleLabel: { color: "#11162B", fontSize: 9, fontWeight: "800" },
  pillName: { flexShrink: 1, color: colors.foreground, fontSize: 11, fontWeight: "700" },
});
