import { useState } from "react";
import { Pressable, Switch, Text, View } from "react-native";
import { marketUiStyles as styles } from "./marketUiStyles";
import { useMarketGate } from "./useMarketGate";

export function MarketGateBar() {
  const { marketOpen, canManage, toggling, error, setOpen } = useMarketGate();
  const [infoOpen, setInfoOpen] = useState(false);
  const hint = marketOpen
    ? "Rosa e asta sono attive. Gli scambi restano sempre disponibili."
    : "Rosa e asta sono bloccate. Gli scambi restano disponibili.";

  return (
    <View style={styles.gateBar} testID="market-gate-bar">
      <View style={styles.gateRow}>
        <Text style={styles.gateTitle} numberOfLines={1}>
          Mercato
        </Text>
        <View style={[styles.gateStatus, marketOpen ? styles.gateStatusOpen : styles.gateStatusClosed]}>
          <Text style={styles.gateStatusLabel}>{marketOpen ? "aperto" : "chiuso"}</Text>
        </View>
        <Pressable
          style={styles.gateInfo}
          accessibilityRole="button"
          accessibilityLabel="Informazioni sul mercato"
          testID="market-gate-info"
          onPress={() => setInfoOpen((open) => !open)}
        >
          <Text style={styles.gateInfoLabel}>i</Text>
        </Pressable>
        <View style={styles.gateSpacer} />
        {canManage ? (
          <Switch
            value={marketOpen}
            disabled={toggling}
            onValueChange={(value) => void setOpen(value)}
            accessibilityLabel="Apri o chiudi il mercato"
            testID="market-gate-switch"
          />
        ) : null}
      </View>
      {infoOpen ? (
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
