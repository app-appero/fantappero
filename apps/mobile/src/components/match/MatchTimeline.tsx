import { theme } from "@fantappero/ui/theme";
import { type ReactNode } from "react";
import { StyleSheet, Text, View } from "react-native";

const { colors, spacing, typography, radius } = theme;

export type TimelineEventItem = {
  type: "event";
  id: string;
  side: "home" | "away";
  minuteLabel: string;
  icon?: ReactNode;
  headline: ReactNode;
  detail?: ReactNode;
};

export type TimelineMarkerItem = {
  type: "marker";
  id: string;
  label: string;
};

export type TimelineEntry = TimelineEventItem | TimelineMarkerItem;

export type MatchTimelineProps = {
  entries: readonly TimelineEntry[];
  homeLabel: string;
  awayLabel: string;
  emptyMessage?: string;
  testID?: string;
};

/**
 * Timeline verticale casa/ospite con minuto al centro, porting mobile di
 * `packages/ui`'s `MatchTimeline` (EP13-P04-quater §9/§10/§12).
 */
export function MatchTimeline({ entries, homeLabel, awayLabel, emptyMessage, testID }: MatchTimelineProps) {
  if (entries.length === 0) {
    return (
      <Text style={styles.empty} testID="match-timeline-empty">
        {emptyMessage ?? "Nessun evento disponibile."}
      </Text>
    );
  }

  return (
    <View testID={testID ?? "match-timeline"}>
      <View style={styles.header}>
        <Text style={styles.headerSide}>{homeLabel}</Text>
        <Text style={[styles.headerSide, styles.headerSideAway]}>{awayLabel}</Text>
      </View>
      {entries.map((entry) =>
        entry.type === "marker" ? (
          <View key={entry.id} style={styles.markerRow} testID="timeline-marker">
            <Text style={styles.markerLabel}>{entry.label}</Text>
          </View>
        ) : (
          <View key={entry.id} style={styles.row} testID={`timeline-event-${entry.id}`}>
            <View style={styles.side}>
              {entry.side === "home" ? (
                <View style={styles.contentInnerHome}>
                  <View style={styles.contentRowHome}>
                    <Text style={styles.headline}>{entry.headline}</Text>
                    {entry.icon}
                  </View>
                  {entry.detail ? <Text style={styles.detailHome}>{entry.detail}</Text> : null}
                </View>
              ) : null}
            </View>
            <View style={styles.minuteWrap}>
              <Text style={styles.minute}>{entry.minuteLabel}</Text>
            </View>
            <View style={styles.side}>
              {entry.side === "away" ? (
                <View style={styles.contentInner}>
                  <View style={styles.contentRow}>
                    {entry.icon}
                    <Text style={styles.headline}>{entry.headline}</Text>
                  </View>
                  {entry.detail ? <Text style={styles.detail}>{entry.detail}</Text> : null}
                </View>
              ) : null}
            </View>
          </View>
        ),
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  header: {
    flexDirection: "row",
    justifyContent: "space-between",
    marginBottom: spacing.sm,
  },
  headerSide: {
    color: colors.foreground,
    fontWeight: "700",
    fontSize: typography.fontSize.sm,
  },
  headerSideAway: {
    textAlign: "right",
  },
  markerRow: {
    paddingVertical: spacing.sm,
    alignItems: "center",
  },
  markerLabel: {
    color: colors.foregroundMuted,
    fontSize: typography.fontSize.xs,
    fontWeight: "700",
    textTransform: "uppercase",
    letterSpacing: 0.5,
  },
  row: {
    flexDirection: "row",
    alignItems: "center",
    minHeight: 44,
  },
  side: {
    flex: 1,
  },
  minuteWrap: {
    paddingHorizontal: spacing.xs,
  },
  minute: {
    backgroundColor: colors.backgroundElevated,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.pill,
    paddingHorizontal: spacing.sm,
    paddingVertical: 1,
    fontSize: typography.fontSize.xs,
    fontWeight: "700",
    color: colors.foreground,
    overflow: "hidden",
  },
  contentInner: {
    alignItems: "flex-start",
  },
  contentInnerHome: {
    alignItems: "flex-end",
  },
  contentRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 4,
  },
  contentRowHome: {
    flexDirection: "row-reverse",
    alignItems: "center",
    gap: 4,
  },
  headline: {
    color: colors.foreground,
    fontWeight: "600",
    fontSize: typography.fontSize.sm,
  },
  detail: {
    color: colors.foregroundMuted,
    fontSize: typography.fontSize.xs,
    textAlign: "left",
  },
  detailHome: {
    color: colors.foregroundMuted,
    fontSize: typography.fontSize.xs,
    textAlign: "right",
  },
  empty: {
    color: colors.foregroundMuted,
  },
});
