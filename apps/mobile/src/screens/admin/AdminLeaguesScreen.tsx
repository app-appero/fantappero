import type { PaginatedAdminLeagues } from "@fantappero/contracts";
import { useCallback, useEffect, useState } from "react";
import { Pressable, Text, TextInput, View } from "react-native";
import { fetchAdminLeagues } from "../../api/admin";
import { ApiError } from "../../api/client";
import { adminUiStyles as styles } from "../../admin/adminUiStyles";
import { UiStatePanel } from "../../components/UiStatePanel";
import { PageContainer } from "../../layout/PageContainer";
import { getApiErrorMessage, useAuthSession } from "../../session/DemoSessionContext";

/** Elenco leghe globale — mobile port of `apps/web/src/pages/AdminLeaguesPage.tsx` (EP11-04a). */
export function AdminLeaguesScreen() {
  const { accessToken } = useAuthSession();

  const [query, setQuery] = useState("");
  const [debouncedQuery, setDebouncedQuery] = useState("");
  const [page, setPage] = useState(1);
  const [result, setResult] = useState<PaginatedAdminLeagues | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);

  useEffect(() => {
    const timer = setTimeout(() => {
      setPage(1);
      setDebouncedQuery(query.trim());
    }, 300);
    return () => clearTimeout(timer);
  }, [query]);

  const load = useCallback(
    async (options?: { silent?: boolean }) => {
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
        setResult(
          await fetchAdminLeagues(accessToken, {
            query: debouncedQuery || undefined,
            page,
          }),
        );
      } catch (loadError) {
        if (loadError instanceof ApiError && loadError.status === 403) {
          setError("Non hai i permessi per consultare le leghe.");
        } else {
          setError(getApiErrorMessage(loadError, "Impossibile caricare le leghe."));
        }
        setResult(null);
      } finally {
        setLoading(false);
      }
    },
    [accessToken, debouncedQuery, page],
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

  return (
    <PageContainer
      title="Leghe"
      testID="screen-admin-leagues"
      refreshing={refreshing}
      onRefresh={onRefresh}
    >
      <TextInput
        style={styles.input}
        value={query}
        onChangeText={setQuery}
        placeholder="Cerca per nome lega"
        autoCapitalize="none"
        autoCorrect={false}
        testID="admin-leagues-query"
      />

      {loading ? (
        <UiStatePanel
          state="loading"
          title="Caricamento leghe"
          message="Ricerca leghe in corso…"
          testID="admin-leagues-loading"
        />
      ) : null}
      {!loading && error ? (
        <UiStatePanel
          state={error.includes("permessi") ? "forbidden" : "error"}
          title="Leghe non disponibili"
          message={error}
          testID="admin-leagues-error"
        />
      ) : null}
      {!loading && !error && result?.items.length === 0 ? (
        <UiStatePanel
          state="empty"
          title="Nessuna lega trovata"
          message="Modifica la ricerca o riprova più tardi."
          testID="admin-leagues-empty"
        />
      ) : null}
      {!loading && !error && result && result.items.length > 0 ? (
        <View testID="admin-leagues-list">
          {result.items.map((league) => (
            <View key={league.id} style={styles.listRow} testID={`admin-league-${league.id}`}>
              <Text style={styles.name}>{league.name}</Text>
              <Text style={styles.meta}>{league.state}</Text>
              <Text style={styles.meta}>{league.ownerDisplayName ?? "—"}</Text>
            </View>
          ))}
          {result.totalPages > 1 ? (
            <View style={styles.rowActions}>
              <Pressable
                style={[styles.secondaryButton, page <= 1 && styles.disabled]}
                disabled={page <= 1}
                onPress={() => setPage((current) => Math.max(1, current - 1))}
                testID="admin-leagues-prev-page"
              >
                <Text style={styles.secondaryButtonLabel}>Pagina precedente</Text>
              </Pressable>
              <Text style={styles.meta}>
                Pagina {result.page} di {result.totalPages} ({result.total} leghe)
              </Text>
              <Pressable
                style={[styles.secondaryButton, page >= result.totalPages && styles.disabled]}
                disabled={page >= result.totalPages}
                onPress={() => setPage((current) => Math.min(result.totalPages, current + 1))}
                testID="admin-leagues-next-page"
              >
                <Text style={styles.secondaryButtonLabel}>Pagina successiva</Text>
              </Pressable>
            </View>
          ) : null}
        </View>
      ) : null}
    </PageContainer>
  );
}
