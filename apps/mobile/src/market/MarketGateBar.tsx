import Feather from "@expo/vector-icons/Feather";
import { theme } from "@fantappero/ui/theme";
import { useState } from "react";
import { Pressable, Switch, Text, View } from "react-native";
import { marketUiStyles as styles } from "./marketUiStyles";
import { useMarketGate } from "./useMarketGate";

export function MarketGateBar({ reloadToken = 0 }: { reloadToken?: number } = {}) {
  const { marketOpen, canManage, toggling, error, setOpen, notFullNotice, switchLocked } =
    useMarketGate({ reloadToken });
  const [infoOpen, setInfoOpen] = useState(false);
  const running = marketOpen && !notFullNotice;
  const hint =
    notFullNotice ??
    (marketOpen
      ? "Rosa e asta sono attive. Gli scambi restano sempre disponibili."
      : "Rosa e asta sono bloccate. Gli scambi restano disponibili.");

  return (
    <View style={styles.gateBar} testID="market-gate-bar">
      <View style={styles.gateRow}>
        <Text style={styles.gateTitle} numberOfLines={1}>
          Mercato
        </Text>
        <View style={[styles.gateStatus, running ? styles.gateStatusOpen : styles.gateStatusClosed]}>
          <Text style={styles.gateStatusLabel}>{running ? "aperto" : "chiuso"}</Text>
        </View>
        <Pressable
          style={styles.gateInfo}
          hitSlop={8}
          accessibilityRole="button"
          accessibilityLabel="Informazioni sul mercato"
          testID="market-gate-info"
          onPress={() => setInfoOpen((open) => !open)}
        >
          <Feather name="info" size={18} color={theme.colors.accent} />
        </Pressable>
        <View style={styles.gateSpacer} />
        {canManage ? (
          <Switch
            value={marketOpen}
            disabled={toggling || switchLocked}
            onValueChange={(value) => void setOpen(value)}
            accessibilityLabel="Mercato aperto"
            testID="market-gate-switch"
          />
        ) : null}
      </View>
      {/* Lega non al completo (20/11): il motivo resta sempre visibile, non solo nell'info. */}
      {notFullNotice ? (
        <Text style={styles.gateNotice} testID="market-gate-not-full" accessibilityRole="alert">
          {notFullNotice}
        </Text>
      ) : infoOpen ? (
        <Text style={styles.gateHint} testID="market-gate-hint">
          {hint}
        </Text>
      ) : null}
      {error ? (
        <Text style={styles.error} testID="market-gate-error">
          {error}
        </Text>
      ) : null}
    </View>
  );
}
