import { LOGIN_CARDS, LOGIN_SHOWCASE_LEAGUES } from "@fantappero/contracts";
import { theme } from "@fantappero/ui/theme";
import { StyleSheet, Text, View } from "react-native";

const { colors, spacing } = theme;

const TONE: Record<(typeof LOGIN_CARDS)[number]["tone"], string> = { blue: "#1F4FC0", violet: "#5B34B8", pink: "#B82C60" };

/** Accesso solo Google: tre carte giocatore a ventaglio, titolo e sigle dei 5 campionati. */
export function LoginCards({ firstName }: { firstName?: string }) {
  return (
    <View style={styles.wrap} testID="login-showcase">
      <View style={styles.stage} accessibilityElementsHidden importantForAccessibility="no-hide-descendants">
        {LOGIN_CARDS.map((card, index) => (
          <View key={card.name} style={[styles.card, { backgroundColor: TONE[card.tone] }, CARD_POS[index]]}>
            <View style={styles.top}>
              <Text style={styles.vote}>{card.vote}</Text>
              <View style={styles.code}>
                <Text style={styles.codeLabel}>{card.code}</Text>
              </View>
            </View>
            <View style={styles.initialWrap}>
              <Text style={styles.initial}>{card.name.charAt(0)}</Text>
            </View>
            <View style={styles.foot}>
              <View style={styles.role}>
                <Text style={styles.roleLabel}>{card.role}</Text>
              </View>
              <Text style={styles.name} numberOfLines={1}>
                {card.name}
              </Text>
            </View>
          </View>
        ))}
      </View>
      <Text style={styles.title}>
        {firstName ? (
          <>
            Bentornato, <Text style={styles.accent}>{firstName}</Text>
          </>
        ) : (
          <>
            Schiera i migliori <Text style={styles.accent}>d&apos;Europa</Text>
          </>
        )}
      </Text>
      <Text style={styles.sub}>Serie A, Premier, LaLiga, Bundesliga e Ligue 1 in una sola lega.</Text>
      <View style={styles.codes}>
        {LOGIN_SHOWCASE_LEAGUES.map((league) => (
          <View key={league.code} style={styles.codeChip}>
            <Text style={styles.codeChipLabel}>{league.code}</Text>
          </View>
        ))}
      </View>
    </View>
  );
}

const CARD_POS = [
  { left: 0, top: 36, transform: [{ rotate: "-10deg" }], zIndex: 1 },
  { left: "29%" as const, top: 0, zIndex: 3 },
  { right: 0, top: 38, transform: [{ rotate: "9deg" }], zIndex: 2 },
];

const styles = StyleSheet.create({
  wrap: { gap: spacing.sm, marginTop: spacing.sm },
  stage: { height: 228, marginBottom: spacing.sm },
  card: {
    position: "absolute",
    width: 142,
    height: 196,
    borderRadius: 20,
    borderWidth: 2,
    borderColor: "rgba(255,255,255,0.35)",
    padding: 12,
  },
  top: { flexDirection: "row", justifyContent: "space-between", alignItems: "flex-start" },
  vote: { color: "#ffffff", fontSize: 34, fontWeight: "800", fontStyle: "italic", lineHeight: 36 },
  code: { backgroundColor: "rgba(255,255,255,0.2)", borderRadius: 6, paddingHorizontal: 6, paddingVertical: 2 },
  codeLabel: { color: "#ffffff", fontSize: 10, fontWeight: "800", letterSpacing: 0.8 },
  initialWrap: { flex: 1, alignItems: "center", justifyContent: "center" },
  initial: { color: "rgba(255,255,255,0.9)", fontSize: 76, fontWeight: "800", fontStyle: "italic" },
  foot: { flexDirection: "row", alignItems: "center", gap: 6 },
  role: { width: 20, height: 20, borderRadius: 10, backgroundColor: "#FF6B8A", alignItems: "center", justifyContent: "center" },
  roleLabel: { color: "#11162B", fontSize: 10, fontWeight: "800" },
  name: { flexShrink: 1, color: "#ffffff", fontSize: 14, fontWeight: "800", fontStyle: "italic", textTransform: "uppercase" },
  title: { color: colors.foreground, fontSize: 36, lineHeight: 38, fontWeight: "800", fontStyle: "italic", letterSpacing: -0.5 },
  accent: { color: "#9DB4FF" },
  sub: { color: colors.foregroundMuted, fontSize: 15 },
  codes: { flexDirection: "row", gap: 8, marginTop: 2 },
  codeChip: { backgroundColor: "rgba(255,255,255,0.1)", borderRadius: 6, paddingHorizontal: 8, paddingVertical: 3 },
  codeChipLabel: { color: colors.foreground, fontSize: 11, fontWeight: "800", letterSpacing: 0.8 },
});
