import type { AdminListoneEntry, FantasyRole } from "@fantappero/contracts";
import { theme } from "@fantappero/ui/theme";
import { useCallback, useEffect, useMemo, useState } from "react";
import { Pressable, Text, TextInput, View } from "react-native";
import { fetchAdminListone, refreshAdminListone } from "../../api/admin";
import { ApiError } from "../../api/client";
import { adminUiStyles as styles } from "../../admin/adminUiStyles";
import { StatusBadge } from "../../components/StatusBadge";
import { UiStatePanel } from "../../components/UiStatePanel";
import { PageContainer } from "../../layout/PageContainer";
import { getApiErrorMessage, useAuthSession } from "../../session/DemoSessionContext";

const { colors } = theme;

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

function roleBadgeColor(role: FantasyRole): string {
  if (role === "P") {
    return colors.success;
  }
  if (role === "D") {
    return colors.warning;
  }
  if (role === "C") {
    return colors.accent;
  }
  return colors.danger;
}

function filterByTab(entries: AdminListoneEntry[], tab: RoleTab): AdminListoneEntry[] {
  if (tab === "all") {
    return entries;
  }
  return entries.filter((entry) => entry.officialRole === tab);
}

const CURRENT_YEAR = new Date().getFullYear();

// The global listone can hold thousands of athletes across every
// competition. Rendering it as plain Views with no virtualization (this
// screen scrolls inside a plain ScrollView, so a FlatList wouldn't help
// here — see apps/mobile/src/screens/roster/RosterAdminManualCard.tsx)
// mounts too many native views at once and gets the app killed for
// excessive memory use on a real device.
const LISTONE_RENDER_LIMIT = 60;

/** Listone ufficiale globale — mobile port of `apps/web/src/pages/AdminListonePage.tsx` (EP11-05). */
export function AdminListoneScreen() {
  const { accessToken } = useAuthSession();

  const [seasonYear, setSeasonYear] = useState(String(CURRENT_YEAR));
  const [entries, setEntries] = useState<AdminListoneEntry[]>([]);
  const [activeTab, setActiveTab] = useState<RoleTab>("all");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [refreshingListone, setRefreshingListone] = useState(false);
  const [refreshProgress, setRefreshProgress] = useState<{
    percent: number;
    stage: string;
    message: string;
  } | null>(null);
  const [refreshError, setRefreshError] = useState<string | null>(null);
  const [refreshSuccess, setRefreshSuccess] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);

  const load = useCallback(
    async (options?: { silent?: boolean }) => {
      const year = Number(seasonYear);
      if (!Number.isInteger(year) || year < 2000) {
        setError("Inserisci un anno stagione valido.");
        setLoading(false);
        return;
      }
      if (!options?.silent) {
        setLoading(true);
      }
      setError(null);
      if (!accessToken) {
        setError("Sessione non disponibile. Accedi di nuovo.");
        setLoading(false);
        return;
      }
      try {
        setEntries(await fetchAdminListone(accessToken, year));
      } catch (loadError) {
        if (loadError instanceof ApiError && loadError.status === 403) {
          setError("Non hai i permessi per consultare il listone.");
        } else {
          setError(getApiErrorMessage(loadError, "Impossibile caricare il listone."));
        }
        setEntries([]);
      } finally {
        setLoading(false);
      }
    },
    [accessToken, seasonYear],
  );

  useEffect(() => {
    void load();
  }, [load]);

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    try {
      await load({ silent: true });
    } finally {
      setRefreshing(false);
    }
  }, [load]);

  async function onRefreshListone() {
    const year = Number(seasonYear);
    if (!Number.isInteger(year) || year < 2000) {
      setRefreshError("Inserisci un anno stagione valido.");
      return;
    }
    if (!accessToken) {
      setRefreshError("Sessione non disponibile. Accedi di nuovo.");
      return;
    }
    setRefreshingListone(true);
    setRefreshError(null);
    setRefreshSuccess(null);
    setRefreshProgress({ percent: 0, stage: "queued", message: "Avvio in corso…" });
    try {
      const result = await refreshAdminListone(accessToken, year, {
        onProgress: (progress) =>
          setRefreshProgress({
            percent: progress.percent,
            stage: progress.stage,
            message: progress.message,
          }),
      });
      setRefreshSuccess(
        `${result.message} Creati: ${result.counters.listoneCreated}, aggiornati: ${result.counters.listoneUpdated}.`,
      );
      await load();
    } catch (refreshErr) {
      setRefreshError(getApiErrorMessage(refreshErr, "Aggiornamento listone non riuscito."));
    } finally {
      setRefreshingListone(false);
      setRefreshProgress(null);
    }
  }

  const visibleEntries = useMemo(() => filterByTab(entries, activeTab), [activeTab, entries]);

  return (
    <PageContainer
      title="Listone ufficiale"
      testID="screen-admin-listone"
      refreshing={refreshing}
      onRefresh={onRefresh}
    >
      <View style={styles.section} testID="admin-listone-card">
        <View style={styles.rowActions}>
          <View style={{ flex: 1, minWidth: 120 }}>
            <Text style={styles.meta}>Stagione</Text>
            <TextInput
              style={styles.input}
              value={seasonYear}
              onChangeText={setSeasonYear}
              keyboardType="numeric"
              testID="admin-listone-season-year"
            />
          </View>
          <Pressable
            style={[styles.button, refreshingListone && styles.disabled]}
            disabled={refreshingListone}
            onPress={() => void onRefreshListone()}
            testID="admin-listone-refresh"
          >
            <Text style={styles.buttonLabel}>Aggiorna listone dal provider</Text>
          </Pressable>
        </View>

        {refreshingListone ? (
          <UiStatePanel
            state="loading"
            title="Aggiornamento in corso"
            message={
              refreshProgress
                ? `${refreshProgress.message} (${refreshProgress.percent}%)`
                : "Avvio in corso…"
            }
            testID="admin-listone-refresh-progress"
          />
        ) : null}
        {!refreshingListone && refreshError ? (
          <UiStatePanel
            state="error"
            title="Aggiornamento non riuscito"
            message={refreshError}
            testID="admin-listone-refresh-error"
          />
        ) : null}
        {!refreshingListone && refreshSuccess ? (
          <UiStatePanel
            state="success"
            title="Listone aggiornato"
            message={refreshSuccess}
            testID="admin-listone-refresh-success"
          />
        ) : null}

        {loading ? (
          <UiStatePanel
            state="loading"
            title="Caricamento listone"
            message="Recupero calciatori e ruoli…"
            testID="admin-listone-loading"
          />
        ) : null}
        {!loading && error ? (
          <UiStatePanel
            state={error.includes("permessi") ? "forbidden" : "error"}
            title="Listone non disponibile"
            message={error}
            testID="admin-listone-error"
          />
        ) : null}

        {!loading && !error ? (
          <View>
            <View style={styles.chipRow} testID="admin-listone-tabs">
              {ROLE_TABS.map((tab) => (
                <Pressable
                  key={tab.value}
                  style={[styles.chip, activeTab === tab.value && styles.chipActive]}
                  onPress={() => setActiveTab(tab.value)}
                  testID={`admin-listone-tab-${tab.value}`}
                >
                  <Text
                    style={[
                      styles.chipLabel,
                      activeTab === tab.value && styles.chipLabelActive,
                    ]}
                  >
                    {tab.label}
                  </Text>
                </Pressable>
              ))}
            </View>

            {visibleEntries.length === 0 ? (
              <UiStatePanel
                state="empty"
                title="Nessun calciatore"
                message="Il listone è vuoto per questa stagione. Aggiornalo dal provider."
                testID={`admin-listone-empty-${activeTab}`}
              />
            ) : (
              <View testID={`admin-listone-table-${activeTab}`}>
                {visibleEntries.length > LISTONE_RENDER_LIMIT ? (
                  <Text style={styles.meta} testID="admin-listone-truncated">
                    Mostrati i primi {LISTONE_RENDER_LIMIT} di {visibleEntries.length} calciatori.
                    Usa i filtri ruolo per restringere l'elenco.
                  </Text>
                ) : null}
                {visibleEntries.slice(0, LISTONE_RENDER_LIMIT).map((entry) => (
                  <View key={entry.athleteId} style={styles.listRow}>
                    <View style={styles.identityRow}>
                      <Text style={styles.name}>{entry.canonicalName}</Text>
                      <StatusBadge
                        label={entry.officialRole}
                        color={roleBadgeColor(entry.officialRole)}
                        textColor={colors.accentContrast}
                      />
                    </View>
                    <Text style={styles.meta}>{ROLE_LABEL[entry.officialRole]}</Text>
                    <Text style={styles.meta}>Club: {entry.clubName ?? "—"}</Text>
                    <Text style={styles.meta}>
                      Posizione provider: {entry.providerPositionRaw ?? "—"}
                    </Text>
                  </View>
                ))}
              </View>
            )}
          </View>
        ) : null}
      </View>
    </PageContainer>
  );
}
