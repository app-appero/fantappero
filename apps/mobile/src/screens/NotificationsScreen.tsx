import type { NotificationItem } from "@fantappero/contracts";
import { theme } from "@fantappero/ui/theme";
import { useNavigation, type NavigationProp } from "@react-navigation/core";
import { useCallback, useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import {
  fetchNotifications,
  markAllNotificationsRead,
  markNotificationRead,
} from "../api/notifications";
import { UiStatePanel } from "../components/UiStatePanel";
import { useScreenData } from "../hooks/useScreenData";
import { PageContainer } from "../layout/PageContainer";
import type { RootStackParamList } from "../navigation/types";
import { getApiErrorMessage, useAuthSession } from "../session/DemoSessionContext";

const { colors, spacing, typography, radius } = theme;

const CATEGORY_LABELS: Record<string, string> = {
  sistema: "Sistema",
  formazione: "Formazione",
  mercato: "Mercato",
  risultati: "Risultati",
};

/** Deep link interni → destinazione mobile equivalente (EP13-P07). */
const DEEP_LINK_ROUTES: Record<string, keyof RootStackParamList> = {
  "/inviti": "ReceivedInvites",
};

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
  const { accessToken } = useAuthSession();

  const [items, setItems] = useState<NotificationItem[]>([]);
  const [unreadCount, setUnreadCount] = useState(0);
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
    const route = item.deepLink ? DEEP_LINK_ROUTES[item.deepLink] : undefined;
    if (route) {
      navigation.navigate(route as never);
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

          {actionError ? (
            <Text style={styles.error} testID="notifications-action-error">
              {actionError}
            </Text>
          ) : null}

          {items.length === 0 ? (
            <UiStatePanel
              state="empty"
              title="Nessuna notifica"
              message="Qui compariranno inviti, scadenze formazione ed esiti di mercato."
              testID="notifications-empty"
            />
          ) : (
            items.map((item) => (
              <Pressable
                key={item.id}
                accessibilityRole="button"
                accessibilityLabel={`${item.title}${item.read ? "" : ", non letta"}`}
                onPress={() => void onOpen(item)}
                style={[styles.card, !item.read && styles.cardUnread]}
                testID={`notification-${item.id}`}
              >
                <Text style={styles.category}>
                  {CATEGORY_LABELS[item.category] ?? item.category}
                  {item.read ? "" : " · non letta"}
                </Text>
                <Text style={styles.title}>{item.title}</Text>
                <Text style={styles.body}>{item.body}</Text>
                <Text style={styles.meta}>{formatDateTime(item.createdAt)}</Text>
              </Pressable>
            ))
          )}
        </View>
      ) : null}
    </PageContainer>
  );
}

const styles = StyleSheet.create({
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
    borderRadius: radius.md,
    padding: spacing.sm,
    gap: spacing.xs,
    backgroundColor: colors.backgroundElevated,
  },
  cardUnread: {
    borderColor: colors.accent,
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
    borderRadius: radius.md,
    paddingHorizontal: spacing.sm,
    paddingVertical: spacing.xs,
  },
  secondaryLabel: {
    color: colors.foreground,
    fontSize: typography.fontSize.sm,
  },
});
