import { pitchRoleFullLabel, resolvePitchRole, type PitchRole } from "@fantappero/contracts";
import { theme } from "@fantappero/ui/theme";
import { StyleSheet, Text, View } from "react-native";

const { colors } = theme;

const COLOR_BY_ROLE: Record<PitchRole, string> = {
  GK: colors.success,
  DEF: colors.warning,
  MID: colors.accent,
  FWD: colors.danger,
};

export type RoleBadgeProps = {
  code: string | null | undefined;
  testID?: string;
};

/**
 * Badge ruolo unico per l'app mobile: stesso colore per lo stesso ruolo
 * canonico sia per i codici provider (G/D/M/F) sia fantacalcio (P/D/C/A)
 * (EP13-P04-quater §1), a parità di logica con `apps/web`.
 */
export function RoleBadge({ code, testID }: RoleBadgeProps) {
  const role = resolvePitchRole(code);
  const color = role ? COLOR_BY_ROLE[role] : colors.foregroundMuted;
  return (
    <View
      style={[styles.badge, { backgroundColor: color }]}
      testID={testID}
      accessibilityLabel={pitchRoleFullLabel(code)}
    >
      <Text style={styles.label}>{code ?? "?"}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  badge: {
    paddingHorizontal: 6,
    paddingVertical: 1,
    borderRadius: 999,
    alignSelf: "flex-start",
  },
  label: {
    color: colors.accentContrast,
    fontSize: 10,
    fontWeight: "700",
  },
});
