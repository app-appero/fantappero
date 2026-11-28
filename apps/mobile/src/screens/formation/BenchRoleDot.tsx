import { lazyStyles } from "../../theme/lazyStyles";
import { pitchRoleFullLabel } from "@fantappero/contracts";
import { theme } from "@fantappero/ui/theme";
import { StyleSheet, Text, View } from "react-native";
import { roleRingColor } from "./FormationParts";

const { colors } = theme;

/**
 * Sigla del ruolo (P, D, C, A) in un cerchio colorato, prima del nome in panchina e in tribuna
 * (1.5, Rosario 27/11). È lo stesso cerchio del «Cambia» e del sito: portiere verde, difensore
 * ambra, centrocampista azzurro, attaccante rosso. Lo stile della riga resta quello dell'app.
 */
export function BenchRoleDot({ role, testID }: { role: string | null | undefined; testID?: string }) {
  return (
    <View
      style={[styles.dot, { backgroundColor: roleRingColor(role) }]}
      accessibilityLabel={`Ruolo: ${pitchRoleFullLabel(role)}`}
      testID={testID}
    >
      <Text style={styles.text} allowFontScaling={false}>
        {role ?? "?"}
      </Text>
    </View>
  );
}

const styles = lazyStyles(() =>
  StyleSheet.create({
    dot: { width: 24, height: 24, borderRadius: 12, alignItems: "center", justifyContent: "center" },
    // Come il cerchio del «Cambia»: lettera scura nel tema scuro, bianca nel chiaro.
    text: { color: colors.accentContrast, fontSize: 12, fontWeight: "800", fontStyle: "italic" },
  }),
);
