import { lazyStyles } from "../theme/lazyStyles";
import type { NotificationItem } from "@fantappero/contracts";
import { theme } from "@fantappero/ui/theme";
import { useNavigation, type NavigationProp } from "@react-navigation/core";
import { useCallback, useMemo, useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import {
  fetchNotifications,
  markAllNotificationsRead,
  sendTestNotifications,
  markNotificationRead,
} from "../api/notifications";
import { HScroll } from "../components/HScroll";
import { UiStatePanel } from "../components/UiStatePanel";
import { useScreenData } from "../hooks/useScreenData";
import { PageContainer } from "../layout/PageContainer";
import { resolveNotificationRoute } from "../navigation/notificationDestination";
import {
  NOTIFICATION_GROUP_COLOR,
  NOTIFICATION_GROUP_LABEL,
  notificationDayLabel,
  notificationKind,
  type NotificationGroup,
} from "../navigation/notificationKind";
import type { RootStackParamList } from "../navigation/types";
import { getApiErrorMessage, useAuthSession } from "../session/DemoSessionContext";

const { colors, spacing, typography, radius } = theme;

const CATEGORY_LABELS: Record<string, string> = {
  sistema: "Sistema",
  formazione: "Formazione",
  mercato: "Mercato",
  risultati: "Risultati",
};

function formatTime(value: string): string {
  try {
    return new Intl.DateTimeFormat("it-IT", { hour: "2-digit", minute: "2-digit", timeZone: "Europe/Rome" }).format(new Date(value));
  } catch {
    return value;
  }
}

function formatDateTime(value: string): string {
  try {
    return new Intl.DateTimeFormat("it-IT", {
      dateStyle: "medium",
      timeStyle: "short",
      timeZone: "Europe/Rome",
    }).format(new Date(value));
  } catch {
    return value;
  }
}

/** Centro notifiche mobile — parità con la campanella web (EP13-P07). */
export function NotificationsScreen() {
  const navigation = useNavigation<NavigationProp<RootStackParamList>>();
  const { accessToken, can } = useAuthSession();

  const [items, setItems] = useState<NotificationItem[]>([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [filter, setFilter] = useState<"tutte" | NotificationGroup>("tutte");
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!accessToken) {
      setLoading(false);
      setItems([]);
      setLoadError("Sessione non disponibile. Accedi di nuovo.");
      return;
    }
    setLoading(true);
    setLoadError(null);
    try {
      const result = await fetchNotifications(accessToken, { pageSize: 30 });
      setItems(result.items);
      setUnreadCount(result.unreadCount);
    } catch (error) {
      setItems([]);
      setLoadError(getApiErrorMessage(error, "Impossibile caricare le notifiche."));
    } finally {
      setLoading(false);
    }
  }, [accessToken]);

  const { refreshing, onRefresh } = useScreenData(load);

  const visibleItems = useMemo(
    () => (filter === "tutte" ? items : items.filter((row) => notificationKind(row).group === filter)),
    [items, filter],
  );
  const groupedByDay = useMemo(() => {
    const groups: Array<[string, NotificationItem[]]> = [];
    for (const row of visibleItems) {
      const label = notificationDayLabel(row.createdAt);
      const last = groups[groups.length - 1];
      if (last && last[0] === label) {
        last[1].push(row);
      } else {
        groups.push([label, [row]]);
      }
    }
    return groups;
  }, [visibleItems]);

  async function onOpen(item: NotificationItem) {
    setActionError(null);
    if (accessToken && !item.read) {
      try {
        await markNotificationRead(accessToken, item.id);
        setItems((current) =>
          current.map((row) => (row.id === item.id ? { ...row, read: true } : row)),
        );
        setUnreadCount((current) => Math.max(0, current - 1));
      } catch (error) {
        setActionError(getApiErrorMessage(error, "Impossibile segnare come letta."));
      }
    }
    const route = resolveNotificationRoute(item);
    if (route?.kind === "matchup") {
      navigation.navigate("MatchupDetail", { slotId: route.slotId });
    } else if (route?.kind === "stack") {
      navigation.navigate(route.name as never);
    } else if (route?.kind === "tab") {
      navigation.navigate("MainTabs", { screen: route.screen });
    }
  }

  async function onSendSamples() {
    if (!accessToken) {
      return;
    }
    setActionError(null);
    try {
      await sendTestNotifications(accessToken);
      await load();
    } catch (error) {
      setActionError(getApiErrorMessage(error, "Impossibile inviare le notifiche di prova."));
    }
  }

  async function onMarkAll() {
    if (!accessToken) {
      return;
    }
    setActionError(null);
    try {
      await markAllNotificationsRead(accessToken);
      setItems((current) => current.map((row) => ({ ...row, read: true })));
      setUnreadCount(0);
    } catch (error) {
      setActionError(getApiErrorMessage(error, "Impossibile segnare tutte come lette."));
    }
  }

  return (
    <PageContainer
      title="Notifiche"
      testID="screen-notifications"
      refreshing={refreshing}
      onRefresh={onRefresh}
    >
      {loading ? (
        <UiStatePanel
          state="loading"
          title="Caricamento notifiche"
          message="Recupero delle notifiche in corso…"
          testID="notifications-loading"
        />
      ) : null}

      {!loading && loadError ? (
        <UiStatePanel
          state="error"
          title="Notifiche non disponibili"
          message={loadError}
          testID="notifications-error"
        />
      ) : null}

      {!loading && !loadError ? (
        <View style={styles.stack}>
          <View style={styles.headerRow}>
            <Text style={styles.body} testID="notifications-unread">
              {unreadCount === 0
                ? "Nessuna notifica non letta"
                : `${unreadCount > 99 ? "99+" : unreadCount} non lette`}
            </Text>
            {unreadCount > 0 ? (
              <Pressable
                accessibilityRole="button"
                onPress={() => void onMarkAll()}
                style={styles.secondaryButton}
                testID="notifications-mark-all"
              >
                <Text style={styles.secondaryLabel}>Segna tutte lette</Text>
              </Pressable>
            ) : null}
          </View>

          {can(["global:operate"]) ? (
            <Pressable
              accessibilityRole="button"
              onPress={() => void onSendSamples()}
              style={styles.secondaryButton}
              testID="notifications-send-samples"
            >
              <Text style={styles.secondaryLabel}>Invia notifiche di prova</Text>
            </Pressable>
          ) : null}

          {actionError ? (
            <Text style={styles.error} testID="notifications-action-error">
              {actionError}
            </Text>
          ) : null}

          <HScroll testID="notifications-filters">
            {(["tutte", "giocatori", "scambi", "asta", "formazione", "turni", "sistema"] as const).map((value) => {
              const count =
                value === "tutte"
                  ? items.length
                  : items.filter((row) => notificationKind(row).group === value).length;
              if (value !== "tutte" && count === 0 && filter !== value) {
                return null;
              }
              const active = filter === value;
              return (
                <Pressable
                  key={value}
                  style={[styles.filterPill, active && styles.filterPillActive]}
                  onPress={() => setFilter(value)}
                  accessibilityState={{ selected: active }}
                  testID={`notifications-filter-${value}`}
                >
                  <Text style={[styles.filterLabel, active && styles.filterLabelActive]}>
                    {`${value === "tutte" ? "Tutte" : NOTIFICATION_GROUP_LABEL[value]}${count > 0 ? ` ${count}` : ""}`}
                  </Text>
                </Pressable>
              );
            })}
          </HScroll>

          {visibleItems.length === 0 ? (
            <UiStatePanel
              state="empty"
              title="Nessuna notifica"
              message="Qui compariranno gol e cartellini dei tuoi giocatori, proposte di scambio, asta, scadenze formazione ed esiti dei turni."
              testID="notifications-empty"
            />
          ) : (
            groupedByDay.map(([day, rows]) => (
              <View key={day} style={styles.stack}>
                <Text style={styles.dayLabel}>{day}</Text>
                {rows.map((item) => {
                  const kind = notificationKind(item);
                  const color = NOTIFICATION_GROUP_COLOR[kind.group];
                  return (
                    <Pressable
                      key={item.id}
                      accessibilityRole="button"
                      accessibilityLabel={`${item.title}${item.read ? "" : ", non letta"}`}
                      onPress={() => void onOpen(item)}
                      style={[styles.card, !item.read && styles.cardUnread]}
                      testID={`notification-${item.id}`}
                    >
                      <View style={styles.cardRow}>
                        <View style={[styles.glyphBox, { backgroundColor: color.bg }]}>
                          <Text style={styles.glyph}>{kind.glyph}</Text>
                        </View>
                        <View style={styles.cardText}>
                          <Text style={styles.title}>{item.title}</Text>
                          <Text style={styles.body}>{item.body}</Text>
                          <Text style={styles.meta}>
                            {`${NOTIFICATION_GROUP_LABEL[kind.group]} · ${formatTime(item.createdAt)}`}
                          </Text>
                        </View>
                        {item.read ? null : <View style={styles.unreadDot} testID={`notification-unread-${item.id}`} />}
                      </View>
                    </Pressable>
                  );
                })}
              </View>
            ))
          )}
        </View>
      ) : null}
    </PageContainer>
  );
}

const styles = lazyStyles(() => StyleSheet.create({
  stack: {
    gap: spacing.sm,
  },
  headerRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: spacing.sm,
  },
  card: {
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.xl,
    padding: spacing.md,
    gap: spacing.xs,
    backgroundColor: colors.backgroundElevated,
  },
  cardUnread: {
    borderColor: colors.accentSecondary,
    borderWidth: 2,
  },
  category: {
    color: colors.foregroundMuted,
    fontSize: typography.fontSize.sm,
    fontWeight: "600",
    textTransform: "uppercase",
  },
  title: {
    color: colors.foreground,
    fontSize: typography.fontSize.md,
    fontWeight: "700",
  },
  body: {
    color: colors.foreground,
    fontSize: typography.fontSize.sm,
  },
  meta: {
    color: colors.foregroundMuted,
    fontSize: typography.fontSize.sm,
  },
  error: {
    color: colors.danger,
    fontSize: typography.fontSize.sm,
  },
  secondaryButton: {
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.pill,
    paddingHorizontal: spacing.sm,
    paddingVertical: spacing.xs,
  },
  secondaryLabel: {
    color: colors.foreground,
    fontSize: typography.fontSize.sm,
  },
  filterPill: {
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    borderRadius: radius.pill,
    borderWidth: 1,
    borderColor: colors.border,
  },
  filterPillActive: { backgroundColor: colors.brand, borderColor: colors.brand },
  filterLabel: { color: colors.foreground, fontWeight: "600" },
  filterLabelActive: { color: colors.onBrand },
  dayLabel: {
    color: colors.foregroundMuted,
    fontSize: 12,
    letterSpacing: 1.4,
    textTransform: "uppercase",
    marginTop: spacing.sm,
  },
  cardRow: { flexDirection: "row", alignItems: "flex-start", gap: spacing.sm },
  cardText: { flex: 1, minWidth: 0, gap: 2 },
  glyphBox: { width: 40, height: 40, borderRadius: 13, alignItems: "center", justifyContent: "center" },
  glyph: { fontSize: 20 },
  unreadDot: { width: 10, height: 10, borderRadius: 5, backgroundColor: "#FF6B8A", marginTop: 6 },
}));
