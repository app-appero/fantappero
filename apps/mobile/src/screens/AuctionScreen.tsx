import type { FantasyRole, LeagueListoneEntry } from "@fantappero/contracts";
import { theme } from "@fantappero/ui/theme";
import { useCallback, useMemo, useState } from "react";
import { Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import { fetchLeagueListone } from "../api/leagues";
import { UiStatePanel } from "../components/UiStatePanel";
import { useScreenData } from "../hooks/useScreenData";
import { PageContainer } from "../layout/PageContainer";
import { getApiErrorMessage, useAuthSession } from "../session/DemoSessionContext";

const { colors, spacing, typography, radius } = theme;

type RoleTab = "all" | FantasyRole;

const ROLE_TABS: Array<{ value: RoleTab; label: string }> = [
  { value: "all", label: "Tutti" },
  { value: "P", label: "Portieri" },
  { value: "D", label: "Difensori" },
  { value: "C", label: "Centrocampisti" },
  { value: "A", label: "Attaccanti" },
];

const ROLE_LABEL: Record<FantasyRole, string> = {
  P: "Portiere",
  D: "Difensore",
  C: "Centrocampista",
  A: "Attaccante",
};

function roleBadgeColors(role: FantasyRole): { backgroundColor: string; color: string } {
  if (role === "P") {
    return { backgroundColor: colors.success, color: colors.accentContrast };
  }
  if (role === "D") {
    return { backgroundColor: colors.warning, color: colors.background };
  }
  if (role === "C") {
    return { backgroundColor: colors.accent, color: colors.accentContrast };
  }
  return { backgroundColor: colors.danger, color: colors.accentContrast };
}

function filterByTab(entries: LeagueListoneEntry[], tab: RoleTab): LeagueListoneEntry[] {
  if (tab === "all") {
    return entries;
  }
  return entries.filter((entry) => entry.effectiveRole === tab);
}

/** Asta: wireframe sessione/offerta (M2) + listone ufficiale via API come web. */
export function AuctionScreen() {
  const { can, accessToken, activeLeagueId, activeLeague } = useAuthSession();
  const canManageSession = can(["market:manage"]);

  const [entries, setEntries] = useState<LeagueListoneEntry[]>([]);
  const [tab, setTab] = useState<RoleTab>("all");
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  const loadListone = useCallback(
    async () => {
      if (!activeLeagueId) {
        setLoading(false);
        setEntries([]);
        setLoadError(null);
        return;
      }
      if (!accessToken) {
        setLoading(false);
        setEntries([]);
        setLoadError("Sessione non disponibile. Accedi di nuovo.");
        return;
      }

      setLoading(true);
      setLoadError(null);
      try {
        setEntries(await fetchLeagueListone(accessToken, activeLeagueId));
      } catch (error) {
        setEntries([]);
        setLoadError(getApiErrorMessage(error, "Impossibile caricare il listone."));
      } finally {
        setLoading(false);
      }
    },
    [accessToken, activeLeagueId],
  );

  const { refreshing, onRefresh } = useScreenData(loadListone);

  const visibleEntries = useMemo(() => filterByTab(entries, tab), [entries, tab]);

  return (
    <PageContainer
      title="Asta"
      testID="screen-auction"
      refreshing={refreshing}
      onRefresh={onRefresh}
    >
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
            <Text style={styles.meta}>Disponibile nella fase asta (prossimamente).</Text>
          </View>
        ) : null}

        <View style={styles.section} testID="wireframe-region-auction-bid">
          <Text style={styles.sectionTitle}>Offerta busta chiusa</Text>
          <Text style={styles.footnote}>
            Asta a buste chiuse — offerta visibile solo a te fino alla chiusura. (prossimamente)
          </Text>
        </View>

        <View style={styles.header}>
          <View style={styles.headerText}>
            <Text style={styles.title}>Listone ufficiale</Text>
            <Text style={styles.meta}>
              {activeLeague
                ? `Lega: ${activeLeague.name} · Stagione ${entries[0]?.seasonYear ?? "—"}`
                : "Seleziona una lega dal selettore in alto."}
            </Text>
          </View>
        </View>

        {loading ? (
          <UiStatePanel
            state="loading"
            title="Caricamento listone"
            message="Recupero calciatori e ruoli…"
            testID="auction-listone-loading"
          />
        ) : null}

        {!loading && loadError ? (
          <View style={styles.section}>
            <UiStatePanel
              state="error"
              title="Listone non disponibile"
              message={loadError}
              testID="auction-listone-error"
            />
            <Pressable
              accessibilityRole="button"
              onPress={() => void loadListone()}
              style={styles.secondaryBtn}
              testID="auction-listone-retry"
            >
              <Text style={styles.secondaryBtnLabel}>Ricarica</Text>
            </Pressable>
          </View>
        ) : null}

        {!loading && !loadError && !activeLeagueId ? (
          <UiStatePanel
            state="empty"
            title="Nessuna lega selezionata"
            message="Scegli una lega per consultare il listone."
            testID="auction-listone-no-league"
          />
        ) : null}

        {!loading && !loadError && activeLeagueId ? (
          <>
            <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.tabs}>
              {ROLE_TABS.map((item) => (
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

            {visibleEntries.length === 0 ? (
              <UiStatePanel
                state="empty"
                title="Nessun calciatore"
                message={
                  tab === "all"
                    ? "Il listone è vuoto. Verrà popolato dagli operatori della piattaforma."
                    : `Nessun ${ROLE_LABEL[tab].toLowerCase()} nel listone.`
                }
                testID={`auction-listone-empty-${tab}`}
              />
            ) : (
              <View testID={`auction-listone-table-${tab}`}>
                {visibleEntries.map((entry) => {
                  const roleColors = roleBadgeColors(entry.effectiveRole);
                  return (
                  <View key={entry.athleteId} style={styles.row}>
                    <View style={styles.nameRow}>
                      <View style={[styles.roleBadge, roleColors]}>
                        <Text style={[styles.roleBadgeText, { color: roleColors.color }]}>
                          {entry.effectiveRole}
                        </Text>
                      </View>
                      <Text style={styles.name}>{entry.canonicalName}</Text>
                    </View>
                    <Text style={styles.meta}>
                      {ROLE_LABEL[entry.effectiveRole]} · {entry.clubName ?? "—"}
                    </Text>
                    {entry.providerPositionRaw ? (
                      <Text style={styles.meta}>Provider: {entry.providerPositionRaw}</Text>
                    ) : null}
                    {entry.override ? (
                      <Text style={styles.override}>
                        {entry.override.pending
                          ? `Override dal turno ${entry.override.effectiveFromRound ?? "?"}`
                          : `Override attivo → ${entry.override.role}`}
                      </Text>
                    ) : null}
                  </View>
                  );
                })}
              </View>
            )}
          </>
      ) : null}
    </PageContainer>
  );
}

const styles = StyleSheet.create({
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
    color: colors.accentContrast,
    fontWeight: typography.fontWeight.semibold,
  },
  chipLabelSecondary: {
    color: colors.foreground,
    fontWeight: typography.fontWeight.semibold,
  },
  header: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "flex-start",
    gap: spacing.md,
  },
  headerText: {
    flex: 1,
    gap: spacing.xs,
  },
  title: {
    fontSize: typography.fontSize.xl,
    fontWeight: typography.fontWeight.semibold,
    color: colors.foreground,
  },
  secondaryBtn: {
    minHeight: 44,
    borderWidth: 1,
    borderColor: colors.accent,
    borderRadius: radius.md,
    alignItems: "center",
    justifyContent: "center",
    paddingVertical: spacing.sm,
  },
  secondaryBtnLabel: {
    color: colors.accent,
    fontWeight: typography.fontWeight.semibold,
  },
  tabs: {
    flexGrow: 0,
  },
  tab: {
    minHeight: 40,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    marginRight: spacing.sm,
    borderRadius: radius.md,
    backgroundColor: colors.backgroundElevated,
    justifyContent: "center",
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
    gap: 2,
  },
  nameRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
  },
  roleBadge: {
    minWidth: 28,
    height: 28,
    borderRadius: radius.sm,
    alignItems: "center",
    justifyContent: "center",
    paddingHorizontal: spacing.xs,
  },
  roleBadgeText: {
    fontSize: typography.fontSize.sm,
    fontWeight: typography.fontWeight.semibold,
  },
  name: {
    color: colors.foreground,
    fontWeight: typography.fontWeight.semibold,
    flexShrink: 1,
  },
  meta: {
    color: colors.foregroundMuted,
    fontSize: typography.fontSize.sm,
  },
  override: {
    marginTop: spacing.xs,
    color: colors.warning,
    fontSize: typography.fontSize.sm,
    fontWeight: typography.fontWeight.semibold,
  },
  footnote: {
    color: colors.foregroundMuted,
    fontSize: typography.fontSize.sm,
  },
  disabled: {
    opacity: 0.5,
  },
});
