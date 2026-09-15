import { Switch, Text, View } from "react-native";
import { marketUiStyles as styles } from "./marketUiStyles";
import { useMarketGate } from "./useMarketGate";

export function MarketGateBar() {
  const { marketOpen, canManage, toggling, error, setOpen } = useMarketGate();

  return (
    <View style={styles.gateBar} testID="market-gate-bar">
      <View style={styles.gateRow}>
        <Text style={styles.gateTitle}>
          Mercato {marketOpen ? "aperto" : "chiuso"}
        </Text>
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
      <Text style={styles.gateHint}>
        {marketOpen
          ? "Rosa e asta sono attive. Gli scambi restano sempre disponibili."
          : "Rosa e asta sono bloccate. Gli scambi restano disponibili."}
      </Text>
      {error ? (
        <Text style={styles.error} testID="market-gate-error">
          {error}
        </Text>
      ) : null}
    </View>
  );
}
