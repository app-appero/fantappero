import type { NotificationEventPreference } from "@fantappero/contracts";
import { theme } from "@fantappero/ui/theme";
import { useCallback, useEffect, useState } from "react";
import { Pressable, StyleSheet, Switch, Text, View } from "react-native";
import { fetchNotificationPreferences, updateNotificationPreference } from "../api/notifications";
import { getApiErrorMessage, useAuthSession } from "../session/DemoSessionContext";
import { lazyStyles } from "../theme/lazyStyles";
import { UiStatePanel } from "./UiStatePanel";

const { colors, spacing, radius } = theme;

const GROUPS: Array<{ category: "calciatori" | "sistema"; title: string; hint: string }> = [
  { category: "calciatori", title: "Calciatori", hint: "Per i calciatori della tua rosa e della tua formazione." },
  { category: "sistema", title: "Sistema", hint: "Scambi, asta, formazione e comunicazioni." },
];

const EVENT_GLYPH: Record<string, string> = {
  "calciatori.gol": "⚽",
  "calciatori.assist": "🅰",
  "calciatori.ammonizione": "🟨",
  "calciatori.espulsione": "🟥",
  "calciatori.sostituzione": "🔁",
  "calciatori.infortunio": "🩹",
  "calciatori.squalifica": "⛔",
  "sistema.scambi": "⇄",
  "sistema.asta": "🔨",
  "sistema.formazione": "⏰",
  "sistema.turno_omologato": "🏁",
  "sistema.avvisi_operatori": "📣",
};

type Change = { eventKey: string; inAppEnabled?: boolean; pushEnabled?: boolean };

/** Centro notifiche personale: ogni evento, canali in-app e push separati. */
export function NotificationEventSettings() {
  const { accessToken } = useAuthSession();
  const [events, setEvents] = useState<NotificationEventPreference[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!accessToken) {
      return;
    }
    try {
      const result = await fetchNotificationPreferences(accessToken);
      setEvents(result.events ?? []);
    } catch (e) {
      setError(getApiErrorMessage(e, "Impossibile caricare le preferenze notifiche."));
    }
  }, [accessToken]);

  useEffect(() => {
    void load();
  }, [load]);

  async function change(changes: Change[]) {
    if (!accessToken || !events) {
      return;
    }
    const previous = events;
    setError(null);
    setEvents(
      events.map((row) => {
        const hit = changes.find((c) => c.eventKey === row.eventKey);
        return hit
          ? {
              ...row,
              inAppEnabled: hit.inAppEnabled ?? row.inAppEnabled,
              pushEnabled: hit.pushEnabled ?? row.pushEnabled,
            }
          : row;
      }),
    );
    try {
      let latest = null;
      for (const c of changes) {
        latest = await updateNotificationPreference(accessToken, c);
      }
      if (latest?.events) {
        setEvents(latest.events);
      }
    } catch (e) {
      setEvents(previous);
      setError(getApiErrorMessage(e, "Preferenza non salvata."));
    }
  }

  if (error && !events) {
    return <UiStatePanel state="error" title="Centro notifiche non disponibile" message={error} />;
  }
  if (!events) {
    return <UiStatePanel state="loading" title="Centro notifiche" message="Caricamento preferenze…" />;
  }

  return (
    <View style={styles.wrap} testID="notification-event-settings">
      <Text style={styles.hint}>
        Scegli quali notifiche ricevere, evento per evento: in app e come push. Le email restano solo
        per registrazione e comunicazioni importanti.
      </Text>
      {error ? <Text style={styles.error}>{error}</Text> : null}
      {GROUPS.map((group) => {
        const rows = events.filter((row) => row.category === group.category);
        if (rows.length === 0) {
          return null;
        }
        return (
          <View key={group.category} style={styles.group}>
            <Text style={styles.groupTitle}>{group.title}</Text>
            <Text style={styles.hint}>{group.hint}</Text>
            <View style={styles.bulk}>
              <Pressable
                style={styles.bulkButton}
                onPress={() => void change(rows.map((r) => ({ eventKey: r.eventKey, inAppEnabled: true, pushEnabled: true })))}
              >
                <Text style={styles.bulkLabel}>Attiva tutte</Text>
              </Pressable>
              <Pressable
                style={styles.bulkButton}
                onPress={() => void change(rows.map((r) => ({ eventKey: r.eventKey, inAppEnabled: false, pushEnabled: false })))}
              >
                <Text style={styles.bulkLabel}>Disattiva tutte</Text>
              </Pressable>
            </View>
            <View style={styles.headRow}>
              <View style={styles.flex} />
              <Text style={styles.colLabel}>In app</Text>
              <Text style={styles.colLabel}>Push</Text>
            </View>
            {rows.map((row) => (
              <View key={row.eventKey} style={styles.row}>
                <View style={styles.glyph}>
                  <Text>{EVENT_GLYPH[row.eventKey] ?? "🔔"}</Text>
                </View>
                <Text style={[styles.flex, styles.label]} numberOfLines={1}>
                  {row.label}
                </Text>
                <View style={styles.switchCell}>
                  <Switch
                    value={row.inAppEnabled}
                    onValueChange={(on) => void change([{ eventKey: row.eventKey, inAppEnabled: on }])}
                    trackColor={{ true: colors.brand, false: colors.border }}
                    thumbColor="#ffffff"
                    testID={`notif-event-${row.eventKey}-inapp`}
                  />
                </View>
                <View style={styles.switchCell}>
                  <Switch
                    value={row.pushEnabled}
                    onValueChange={(on) => void change([{ eventKey: row.eventKey, pushEnabled: on }])}
                    trackColor={{ true: colors.brand, false: colors.border }}
                    thumbColor="#ffffff"
                    testID={`notif-event-${row.eventKey}-push`}
                  />
                </View>
              </View>
            ))}
          </View>
        );
      })}
    </View>
  );
}

const styles = lazyStyles(() =>
  StyleSheet.create({
    wrap: { gap: spacing.md },
    group: { gap: spacing.sm },
    groupTitle: { color: colors.foreground, fontSize: 20, fontWeight: "800", fontStyle: "italic", textTransform: "uppercase" },
    hint: { color: colors.foregroundMuted, fontSize: 13 },
    error: { color: "#FF8FA8" },
    flex: { flex: 1, minWidth: 0 },
    bulk: { flexDirection: "row", gap: spacing.sm },
    bulkButton: { paddingHorizontal: spacing.md, paddingVertical: 6, borderRadius: radius.pill, borderWidth: 1, borderColor: colors.border },
    bulkLabel: { color: colors.foreground, fontWeight: "600", fontSize: 13 },
    headRow: { flexDirection: "row", alignItems: "center" },
    colLabel: { width: 64, textAlign: "center", color: colors.foregroundMuted, fontSize: 11, letterSpacing: 1.2, textTransform: "uppercase" },
    row: { flexDirection: "row", alignItems: "center", gap: spacing.sm, paddingVertical: 6, borderTopWidth: 1, borderTopColor: colors.border },
    glyph: { width: 34, height: 34, borderRadius: 11, alignItems: "center", justifyContent: "center", backgroundColor: colors.backgroundElevated },
    label: { color: colors.foreground, fontWeight: "600" },
    switchCell: { width: 64, alignItems: "center" },
  }),
);
