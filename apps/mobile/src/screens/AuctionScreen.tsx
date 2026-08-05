import { useMemo, useState } from "react";
import { Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import { theme } from "@fantappero/ui/theme";
import { UiStatePanel } from "../components/UiStatePanel";
import { PageContainer } from "../layout/PageContainer";
import { useDemoSession } from "../session/DemoSessionContext";

const { colors, spacing, typography, radius } = theme;

type FantasyRole = "P" | "D" | "C" | "A";
type RoleTab = "all" | FantasyRole;

type ListoneRow = {
  id: string;
  name: string;
  role: FantasyRole;
  club: string;
  override?: string;
};

const DEMO_ROWS: ListoneRow[] = [
  { id: "1", name: "Rui Patrício", role: "P", club: "Wolves" },
  { id: "2", name: "C. Coady", role: "D", club: "Wolves" },
  { id: "3", name: "Rúben Neves", role: "C", club: "Wolves", override: "Override attivo → A" },
  { id: "4", name: "R. Jiménez", role: "A", club: "Wolves" },
];

const TABS: Array<{ value: RoleTab; label: string }> = [
  { value: "all", label: "Tutti" },
  { value: "P", label: "Portieri" },
  { value: "D", label: "Difensori" },
  { value: "C", label: "Centrocampisti" },
  { value: "A", label: "Attaccanti" },
];

/** Asta: placeholder sessione/offerta sopra + listone demo sotto (sync live sul web). */
export function AuctionScreen() {
  const { can } = useDemoSession();
  const canManageSession = can(["market:manage"]);
  const isListoneAdmin = can(["league:admin"]);
  const [tab, setTab] = useState<RoleTab>("all");
  const [message, setMessage] = useState<string | null>(null);

  const rows = useMemo(
    () => (tab === "all" ? DEMO_ROWS : DEMO_ROWS.filter((row) => row.role === tab)),
    [tab],
  );

  return (
    <PageContainer title="Asta" testID="screen-auction">
      <ScrollView contentContainerStyle={styles.content}>
        {canManageSession ? (
          <View style={styles.section} testID="wireframe-region-auction-admin">
            <Text style={styles.sectionTitle}>Gestione sessione (admin)</Text>
            <View style={styles.rowActions}>
              <View style={styles.chip}>
                <Text style={styles.chipLabel}>Apri asta</Text>
              </View>
              <View style={[styles.chip, styles.chipSecondary]}>
                <Text style={styles.chipLabelSecondary}>Chiudi asta</Text>
              </View>
            </View>
            <Text style={styles.meta}>Sessione: Aperta · Partecipanti: 6/8</Text>
          </View>
        ) : null}

        <View style={styles.section} testID="wireframe-region-auction-bid">
          <Text style={styles.sectionTitle}>Offerta busta chiusa</Text>
          <Text style={styles.meta}>Budget residuo: 420 crediti</Text>
          <Text style={styles.meta}>Giocatore · Offerta (crediti)</Text>
          <Text style={styles.footnote}>
            Asta a buste chiuse — offerta visibile solo a te fino alla chiusura. (prossimamente)
          </Text>
        </View>

        <View style={styles.header}>
          <Text style={styles.title}>Listone ufficiale</Text>
          {isListoneAdmin ? (
            <Pressable
              style={styles.refreshBtn}
              onPress={() =>
                setMessage(
                  "Aggiornamento live dal provider disponibile via API web. Qui è simulato (demo).",
                )
              }
              testID="auction-listone-refresh"
            >
              <Text style={styles.refreshLabel}>Aggiorna</Text>
            </Pressable>
          ) : null}
        </View>

        {message ? (
          <UiStatePanel
            state="success"
            title="Listone"
            message={message}
            testID="auction-listone-refresh-success"
          />
        ) : null}

        <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.tabs}>
          {TABS.map((item) => (
            <Pressable
              key={item.value}
              onPress={() => setTab(item.value)}
              style={[styles.tab, tab === item.value ? styles.tabActive : null]}
              testID={`auction-tab-${item.value}`}
            >
              <Text style={tab === item.value ? styles.tabLabelActive : styles.tabLabel}>
                {item.label}
              </Text>
            </Pressable>
          ))}
        </ScrollView>

        {rows.length === 0 ? (
          <UiStatePanel
            state="empty"
            title="Nessun calciatore"
            message="Il listone demo è vuoto per questo filtro."
            testID="auction-listone-empty"
          />
        ) : (
          <View testID="auction-listone-table">
            {rows.map((row) => (
              <View key={row.id} style={styles.row}>
                <Text style={styles.name}>{row.name}</Text>
                <Text style={styles.meta}>
                  {row.role} · {row.club}
                  {row.override ? ` · ${row.override}` : ""}
                </Text>
              </View>
            ))}
          </View>
        )}
      </ScrollView>
    </PageContainer>
  );
}

const styles = StyleSheet.create({
  content: {
    gap: spacing.md,
    paddingBottom: spacing.xl,
  },
  section: {
    padding: spacing.md,
    borderRadius: radius.md,
    backgroundColor: colors.backgroundElevated,
    gap: spacing.sm,
  },
  sectionTitle: {
    fontSize: typography.fontSize.lg,
    fontWeight: typography.fontWeight.semibold,
    color: colors.foreground,
  },
  rowActions: {
    flexDirection: "row",
    gap: spacing.sm,
    flexWrap: "wrap",
  },
  chip: {
    backgroundColor: colors.accent,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    borderRadius: radius.md,
  },
  chipSecondary: {
    backgroundColor: colors.background,
    borderWidth: 1,
    borderColor: colors.border,
  },
  chipLabel: {
    color: colors.background,
    fontWeight: typography.fontWeight.semibold,
  },
  chipLabelSecondary: {
    color: colors.foreground,
    fontWeight: typography.fontWeight.semibold,
  },
  header: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    gap: spacing.md,
  },
  title: {
    fontSize: typography.fontSize.xl,
    fontWeight: typography.fontWeight.semibold,
    color: colors.foreground,
    flex: 1,
  },
  refreshBtn: {
    backgroundColor: colors.accent,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    borderRadius: radius.md,
  },
  refreshLabel: {
    color: colors.background,
    fontWeight: typography.fontWeight.semibold,
  },
  tabs: {
    flexGrow: 0,
  },
  tab: {
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    marginRight: spacing.sm,
    borderRadius: radius.md,
    backgroundColor: colors.backgroundElevated,
  },
  tabActive: {
    borderWidth: 1,
    borderColor: colors.accent,
  },
  tabLabel: {
    color: colors.foregroundMuted,
  },
  tabLabelActive: {
    color: colors.foreground,
    fontWeight: typography.fontWeight.semibold,
  },
  row: {
    padding: spacing.md,
    borderRadius: radius.md,
    backgroundColor: colors.backgroundElevated,
    marginBottom: spacing.sm,
  },
  name: {
    color: colors.foreground,
    fontWeight: typography.fontWeight.semibold,
  },
  meta: {
    marginTop: spacing.xs,
    color: colors.foregroundMuted,
    fontSize: typography.fontSize.sm,
  },
  footnote: {
    color: colors.foregroundMuted,
    fontSize: typography.fontSize.sm,
  },
});
