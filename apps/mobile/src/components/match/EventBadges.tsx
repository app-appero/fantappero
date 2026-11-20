import { lazyStyles } from "../../theme/lazyStyles";
import { liveStringMap } from "../../theme/liveColors";
import { MaterialCommunityIcons } from "@expo/vector-icons";
import type { MatchBadge, MatchBadgeKind } from "@fantappero/contracts";
import { darkColors, theme } from "@fantappero/ui/theme";
import { StyleSheet, Text, View } from "react-native";

const { colors } = theme;
/** Il cartellino resta giallo in entrambi i temi, come `YellowCardIcon` sul web. */
const YELLOW_CARD = darkColors.warning;

const ICON_NAME_BY_KIND: Record<MatchBadgeKind, keyof typeof MaterialCommunityIcons.glyphMap> = {
  goal: "soccer",
  ownGoal: "soccer",
  penaltyScored: "soccer",
  penaltyMissed: "close-circle",
  penaltySaved: "hand-back-right",
  assist: "shoe-print",
  yellowCard: "card",
  redCard: "card",
  substitutionIn: "arrow-up-bold-box",
  substitutionOut: "arrow-down-bold-box",
};

// Letti a ogni render: una tabella fissata al caricamento del modulo resterebbe
// con i colori del tema d'avvio anche dopo il cambio tema.
const ICON_COLOR_BY_KIND = liveStringMap<MatchBadgeKind>(() => ({
  goal: colors.foreground,
  ownGoal: colors.danger,
  penaltyScored: colors.foreground,
  penaltyMissed: colors.danger,
  penaltySaved: colors.foreground,
  assist: colors.accent,
  yellowCard: YELLOW_CARD,
  redCard: colors.danger,
  substitutionIn: colors.success,
  substitutionOut: colors.danger,
}));

export type EventBadgesProps = {
  badges: readonly MatchBadge[];
  size?: number;
  testID?: string;
};

/** Riga di badge evento con conteggio (`⚽ ×2`), porting mobile di `packages/ui` (§6/§7). */
export function EventBadges({ badges, size = 14, testID }: EventBadgesProps) {
  if (badges.length === 0) {
    return null;
  }
  return (
    <View style={styles.row} testID={testID}>
      {badges.map((badge) => {
        return (
          <View key={badge.kind} style={styles.item} testID={`event-badge-${badge.kind}`}>
            <MaterialCommunityIcons
              name={ICON_NAME_BY_KIND[badge.kind]}
              size={size}
              color={ICON_COLOR_BY_KIND[badge.kind]}
            />
            {badge.count > 1 ? <Text style={styles.count}>×{badge.count}</Text> : null}
          </View>
        );
      })}
    </View>
  );
}

const styles = lazyStyles(() => StyleSheet.create({
  row: {
    flexDirection: "row",
    alignItems: "center",
    gap: 3,
  },
  item: {
    flexDirection: "row",
    alignItems: "center",
  },
  count: {
    color: colors.foreground,
    fontSize: 9,
    fontWeight: "700",
    marginLeft: 1,
  },
}));
