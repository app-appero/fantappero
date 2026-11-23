import {
  appUsageGroupHint,
  appUsageGroupTitle,
  appUsageSummaryLine,
  appUsageUserName,
  appUsageUserSeen,
  type AdminAppUsage,
  type AdminAppUsageGroup,
} from "@fantappero/contracts";
import { theme } from "@fantappero/ui/theme";
import { useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { adminUiStyles } from "../../admin/adminUiStyles";
import { lazyStyles } from "../../theme/lazyStyles";

const { colors, spacing, typography, radius } = theme;

function groupKey(group: AdminAppUsageGroup): string {
  return `${group.kind}-${group.platform ?? ""}-${group.versionCode ?? ""}-${group.versionName ?? ""}`;
}

/**
 * «Chi ha quale versione» della pagina «Versione app» (release 1.4, Rosario 23/11): gli stessi
 * gruppi e testi del sito (`@fantappero/contracts`), compreso «Sito da Android» per chi usa
 * solo il sito da un telefono Android. Ogni gruppo si apre e chiude toccando il titolo; «App mai
 * usata / solo sito» parte chiuso perché è il più lungo.
 */
export function AppUsageList({ usage, now }: { usage: AdminAppUsage; now?: Date }) {
  const [collapsed, setCollapsed] = useState<ReadonlySet<string>>(
    () => new Set(usage.groups.filter((group) => group.kind === "never").map(groupKey)),
  );
  const at = now ?? new Date();

  function toggle(key: string) {
    setCollapsed((previous) => {
      const next = new Set(previous);
      if (next.has(key)) {
        next.delete(key);
      } else {
        next.add(key);
      }
      return next;
    });
  }

  return (
    <View style={adminUiStyles.section} testID="admin-appversion-users">
      <Text style={adminUiStyles.sectionTitle} accessibilityRole="header">
        Chi ha quale versione
      </Text>
      <Text style={styles.summary} testID="admin-appversion-users-summary">
        {usage.announced
          ? appUsageSummaryLine(usage)
          : `${usage.appUsers} ${usage.appUsers === 1 ? "utente usa" : "utenti usano"} l'app`}
        {` · ${usage.totalUsers} ${usage.totalUsers === 1 ? "utente" : "utenti"} in tutto`}
      </Text>
      {usage.groups.map((group) => {
        const key = groupKey(group);
        const open = !collapsed.has(key);
        const hint = appUsageGroupHint(group);
        return (
          <View key={key} style={styles.group} testID={`admin-appversion-group-${group.kind}`}>
            <Pressable
              accessibilityRole="button"
              accessibilityState={{ expanded: open }}
              accessibilityLabel={`${appUsageGroupTitle(group)}${group.upToDate ? ", aggiornati" : ""}`}
              onPress={() => toggle(key)}
              style={({ pressed }) => [styles.groupHeader, pressed && styles.pressed]}
            >
              <Text style={styles.groupTitle}>{appUsageGroupTitle(group)}</Text>
              {group.upToDate ? <Text style={styles.badge}>aggiornati</Text> : null}
              <Text style={styles.chevron}>{open ? "▾" : "▸"}</Text>
            </Pressable>
            {open && hint ? <Text style={adminUiStyles.meta}>{hint}</Text> : null}
            {open
              ? group.users.map((user) => {
                  const seen = appUsageUserSeen(user, at, group.kind);
                  return (
                    <View key={user.userId} style={styles.user}>
                      <Text style={styles.userName}>{appUsageUserName(user)}</Text>
                      <Text style={adminUiStyles.meta} selectable>
                        {user.email}
                      </Text>
                      {seen ? <Text style={adminUiStyles.meta}>{seen}</Text> : null}
                    </View>
                  );
                })
              : null}
          </View>
        );
      })}
    </View>
  );
}

const styles = lazyStyles(() =>
  StyleSheet.create({
    summary: {
      color: colors.foreground,
      fontSize: typography.fontSize.sm,
      fontWeight: typography.fontWeight.semibold,
    },
    group: {
      gap: spacing.xs,
      borderTopWidth: 1,
      borderTopColor: colors.border,
      paddingTop: spacing.sm,
    },
    groupHeader: {
      minHeight: 44,
      flexDirection: "row",
      alignItems: "center",
      gap: spacing.sm,
    },
    pressed: {
      opacity: 0.75,
    },
    groupTitle: {
      flex: 1,
      color: colors.foreground,
      fontSize: typography.fontSize.md,
      fontWeight: typography.fontWeight.semibold,
    },
    badge: {
      color: colors.success,
      borderColor: colors.success,
      borderWidth: 1,
      borderRadius: radius.pill,
      paddingHorizontal: spacing.sm,
      fontSize: typography.fontSize.xs,
      fontWeight: typography.fontWeight.semibold,
    },
    chevron: {
      color: colors.foregroundMuted,
      fontSize: typography.fontSize.md,
    },
    user: {
      paddingVertical: spacing.xs,
      paddingLeft: spacing.sm,
      borderLeftWidth: 2,
      borderLeftColor: colors.border,
      gap: 2,
    },
    userName: {
      color: colors.foreground,
      fontSize: typography.fontSize.sm,
      fontWeight: typography.fontWeight.semibold,
    },
  }),
);
