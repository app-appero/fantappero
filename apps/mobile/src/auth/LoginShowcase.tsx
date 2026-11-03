import { theme } from "@fantappero/ui/theme";
import { StyleSheet, Text, View } from "react-native";

const { colors, spacing, radius } = theme;

type Dot = { name: string; role: "P" | "D" | "C" | "A"; x: number; y: number; state?: "final" | "live" };

const ROLE_COLOR = { P: "#FFD23F", D: "#38BDF8", C: "#B58CFF", A: "#FF6B8A" } as const;

const PLAYERS: Dot[] = [
  { name: "Lautaro", role: "A", x: 22, y: 14, state: "final" },
  { name: "Lookman", role: "A", x: 50, y: 14, state: "live" },
  { name: "Leao", role: "A", x: 78, y: 14 },
  { name: "Barella", role: "C", x: 26, y: 40, state: "final" },
  { name: "Tonali", role: "C", x: 50, y: 40 },
  { name: "Mkhitaryan", role: "C", x: 74, y: 40 },
  { name: "Bastoni", role: "D", x: 16, y: 66 },
  { name: "Bremer", role: "D", x: 39, y: 66, state: "final" },
  { name: "Theo", role: "D", x: 61, y: 66 },
  { name: "Dumfries", role: "D", x: 84, y: 66 },
  { name: "Maignan", role: "P", x: 50, y: 90 },
];

const FEATURES = [
  { glyph: "🔨", title: "Asta live e scambi", text: "Costruisci la rosa con gli amici", tint: "rgba(255,210,63,0.18)" },
  { glyph: "🔒", title: "Formazione a step", text: "Ogni giocatore si blocca al suo fischio", tint: "rgba(76,134,255,0.18)" },
  { glyph: "🏆", title: "Più campionati", text: "Serie A, Premier e non solo, in una lega", tint: "rgba(181,140,255,0.18)" },
];

/** Schermata di accesso: campo in miniatura e tre schede, per riempire lo spazio sopra «Continua con Google». */
export function LoginShowcase() {
  return (
    <View style={styles.wrap} testID="login-showcase">
      <Text style={styles.tagline}>Ogni giocatore conta, minuto per minuto.</Text>
      <View style={styles.pitch} accessibilityElementsHidden importantForAccessibility="no-hide-descendants">
        <View style={styles.pitchFrame} />
        <View style={styles.halfway} />
        {PLAYERS.map((p) => (
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
      <View style={styles.features}>
        {FEATURES.map((f) => (
          <View key={f.title} style={styles.feature}>
            <View style={[styles.glyph, { backgroundColor: f.tint }]}>
              <Text style={styles.glyphLabel}>{f.glyph}</Text>
            </View>
            <View style={styles.featureText}>
              <Text style={styles.featureTitle}>{f.title}</Text>
              <Text style={styles.featureSub}>{f.text}</Text>
            </View>
          </View>
        ))}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { gap: spacing.md, marginTop: spacing.md },
  tagline: { color: colors.foregroundMuted, fontSize: 15 },
  pitch: {
    height: 210,
    borderRadius: 24,
    overflow: "hidden",
    backgroundColor: "#12795A",
    borderWidth: 1,
    borderColor: "rgba(255,255,255,0.18)",
  },
  pitchFrame: {
    position: "absolute",
    top: 6,
    left: 6,
    right: 6,
    bottom: 6,
    borderWidth: 2,
    borderColor: "rgba(255,255,255,0.28)",
    borderRadius: 8,
  },
  halfway: { position: "absolute", left: 6, right: 6, top: "50%", height: 2, backgroundColor: "rgba(255,255,255,0.28)" },
  slot: { position: "absolute", width: 64, marginLeft: -32, marginTop: -22, alignItems: "center", gap: 2 },
  circle: {
    width: 30,
    height: 30,
    borderRadius: 15,
    borderWidth: 3,
    backgroundColor: "#ffffff",
    alignItems: "center",
    justifyContent: "center",
  },
  circleFinal: { borderColor: "#ffffff", shadowColor: "#ffffff", shadowOpacity: 0.9, shadowRadius: 6, shadowOffset: { width: 0, height: 0 }, elevation: 4 },
  circleLive: { borderColor: "#4C86FF", shadowColor: "#4C86FF", shadowOpacity: 0.9, shadowRadius: 6, shadowOffset: { width: 0, height: 0 }, elevation: 4 },
  initial: { color: "#0A0F22", fontWeight: "800", fontStyle: "italic", fontSize: 13 },
  name: { color: "#ffffff", fontSize: 8, fontWeight: "600", backgroundColor: "rgba(8,12,30,0.78)", borderRadius: 999, paddingHorizontal: 6, overflow: "hidden" },
  badges: { position: "absolute", bottom: 10, left: 10, flexDirection: "row", gap: 6 },
  goal: { backgroundColor: "rgba(8,12,30,0.8)", borderRadius: 999, paddingHorizontal: 9, paddingVertical: 3 },
  goalLabel: { color: "#ffffff", fontSize: 10, fontWeight: "700" },
  vote: { backgroundColor: "#ffffff", borderRadius: 999, paddingHorizontal: 9, paddingVertical: 3 },
  voteLabel: { color: "#11162B", fontSize: 10, fontWeight: "800" },
  features: { gap: 10 },
  feature: {
    flexDirection: "row",
    alignItems: "center",
    gap: 14,
    padding: 12,
    borderRadius: radius.xl,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: "rgba(24,30,60,0.75)",
  },
  glyph: { width: 44, height: 44, borderRadius: 14, alignItems: "center", justifyContent: "center" },
  glyphLabel: { fontSize: 22 },
  featureText: { flex: 1, minWidth: 0 },
  featureTitle: { color: colors.foreground, fontWeight: "700", fontSize: 16 },
  featureSub: { color: colors.foregroundMuted, fontSize: 13 },
});
