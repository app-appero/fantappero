import type { LeagueListoneEntry, LeagueSummary } from "@fantappero/contracts";
import { useMemo } from "react";
import { Pressable, ScrollView, Text, View } from "react-native";
import { UiStatePanel } from "../../components/UiStatePanel";
import { marketUiStyles as styles } from "../../market/marketUiStyles";
import { filterByTab, roleBadgeColors, ROLE_LABEL, ROLE_TABS, type RoleTab } from "./auctionListoneHelpers";

/** Official listone with role tabs — read-only reference table shown below the bid panel (EP08-01/02). */
export function AuctionListone({
  entries,
  loading,
  loadError,
  onRetry,
  activeLeagueId,
  activeLeague,
  tab,
  onTabChange,
}: {
  entries: LeagueListoneEntry[];
  loading: boolean;
  loadError: string | null;
  onRetry: () => void;
  activeLeagueId: string | null;
  activeLeague: LeagueSummary | null;
  tab: RoleTab;
  onTabChange: (tab: RoleTab) => void;
}) {
  const visibleEntries = useMemo(() => filterByTab(entries, tab), [entries, tab]);

  return (
    <View style={styles.section} testID="auction-listone-card">
      <Text style={styles.sectionTitle}>Listone ufficiale</Text>
      <Text style={styles.meta}>
        {activeLeague
          ? `Lega: ${activeLeague.name} · Stagione ${entries[0]?.seasonYear ?? "—"}`
          : "Seleziona una lega dal selettore in alto."}
      </Text>

      {loading ? (
        <UiStatePanel
          state="loading"
          title="Caricamento listone"
          message="Recupero calciatori e ruoli…"
          testID="auction-listone-loading"
        />
      ) : null}

      {!loading && loadError ? (
        <View>
          <UiStatePanel
            state="error"
            title="Listone non disponibile"
            message={loadError}
            testID="auction-listone-error"
          />
          <Pressable style={styles.secondaryButton} onPress={onRetry} testID="auction-listone-retry">
            <Text style={styles.secondaryButtonLabel}>Ricarica</Text>
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
          <ScrollView horizontal showsHorizontalScrollIndicator={false}>
            <View style={styles.chipRow}>
              {ROLE_TABS.map((item) => (
                <Pressable
                  key={item.value}
                  onPress={() => onTabChange(item.value)}
                  style={[styles.chip, tab === item.value ? styles.chipActive : null]}
                  testID={`auction-tab-${item.value}`}
                >
                  <Text style={tab === item.value ? styles.chipLabelActive : styles.chipLabel}>
                    {item.label}
                  </Text>
                </Pressable>
              ))}
            </View>
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
                  <View key={entry.athleteId} style={styles.listRow}>
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
    </View>
  );
}
