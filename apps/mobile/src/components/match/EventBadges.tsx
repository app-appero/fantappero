import { MaterialCommunityIcons } from "@expo/vector-icons";
import type { MatchBadge, MatchBadgeKind } from "@fantappero/contracts";
import { theme } from "@fantappero/ui/theme";
import { StyleSheet, Text, View } from "react-native";

const { colors } = theme;

type IconSpec = { name: keyof typeof MaterialCommunityIcons.glyphMap; color: string };

const ICON_BY_KIND: Record<MatchBadgeKind, IconSpec> = {
  goal: { name: "soccer", color: "#fff" },
  ownGoal: { name: "soccer", color: colors.danger },
  penaltyScored: { name: "soccer", color: "#fff" },
  penaltyMissed: { name: "close-circle", color: colors.danger },
  penaltySaved: { name: "hand-back-right", color: "#fff" },
  assist: { name: "shoe-print", color: colors.accent },
  yellowCard: { name: "card", color: colors.warning },
  redCard: { name: "card", color: colors.danger },
  substitutionIn: { name: "arrow-up-bold-box", color: colors.success },
  substitutionOut: { name: "arrow-down-bold-box", color: colors.danger },
};

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
        const icon = ICON_BY_KIND[badge.kind];
        return (
          <View key={badge.kind} style={styles.item} testID={`event-badge-${badge.kind}`}>
            <MaterialCommunityIcons name={icon.name} size={size} color={icon.color} />
            {badge.count > 1 ? <Text style={styles.count}>×{badge.count}</Text> : null}
          </View>
        );
      })}
    </View>
  );
}

const styles = StyleSheet.create({
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
});
