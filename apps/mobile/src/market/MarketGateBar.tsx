import Feather from "@expo/vector-icons/Feather";
import { theme } from "@fantappero/ui/theme";
import { useState } from "react";
import { Pressable, Switch, Text, View } from "react-native";
import { MARKET_STATUS_BADGE_LABEL } from "./marketGateNotice";
import { marketUiStyles as styles } from "./marketUiStyles";
import { type MarketGateHandle, useMarketGate } from "./useMarketGate";

export function MarketGateBar({ reloadToken = 0 }: { reloadToken?: number } = {}) {
  const gate = useMarketGate({ reloadToken });
  return <MarketGateBarView gate={gate} />;
}

/**
 * La barra con uno stato del mercato già letto: Amministrazione lega lo condivide con il conto
 * degli iscritti, inviti in attesa compresi (Rosario, 20/11).
 */
export function MarketGateBarView({ gate }: { gate: MarketGateHandle }) {
  const { marketOpen, canManage, toggling, error, setOpen, blockedNotice, statusBadge, switchLocked } =
    gate;
  const [infoOpen, setInfoOpen] = useState(false);
  const running = statusBadge === "open";
  // Lega non al completo (20/11) o turno in corso (21/11): il motivo resta sempre visibile.
  const hint =
    blockedNotice ??
    (marketOpen
      ? "Rosa e asta sono attive. Gli scambi restano sempre disponibili."
      : "Rosa e asta sono bloccate. Gli scambi restano disponibili.");

  return (
    <View style={styles.gateBar} testID="market-gate-bar">
      <View style={styles.gateRow}>
        <Text style={styles.gateTitle} numberOfLines={1}>
          Mercato
        </Text>
        <View
          style={[styles.gateStatus, running ? styles.gateStatusOpen : styles.gateStatusClosed]}
          testID="market-gate-status"
          accessibilityLabel={`Mercato ${MARKET_STATUS_BADGE_LABEL[statusBadge]}`}
        >
          <Text style={styles.gateStatusLabel}>{MARKET_STATUS_BADGE_LABEL[statusBadge]}</Text>
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
      {/* Lega non al completo (20/11) o turno in corso (21/11): il motivo resta sempre visibile. */}
      {blockedNotice ? (
        <Text
          style={styles.gateNotice}
          testID={statusBadge === "round_in_progress" ? "market-gate-round" : "market-gate-not-full"}
          accessibilityRole="alert"
        >
          {blockedNotice}
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
