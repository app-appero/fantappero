import type { AdminUser, PaginatedAdminUsers } from "@fantappero/contracts";
import { useCallback, useEffect, useState } from "react";
import { Pressable, Text, TextInput, View } from "react-native";
import { fetchAdminUsers, promoteOperator, revokeOperator } from "../../api/admin";
import { ApiError } from "../../api/client";
import { adminUiStyles as styles } from "../../admin/adminUiStyles";
import { UiStatePanel } from "../../components/UiStatePanel";
import { PageContainer } from "../../layout/PageContainer";
import { getApiErrorMessage, useAuthSession } from "../../session/DemoSessionContext";

type PendingAction = { user: AdminUser; kind: "promote" | "revoke" };

/** Elenco utenti + promuovi/revoca operatore — mobile port of `apps/web/src/pages/AdminUsersPage.tsx` (EP11-04b). */
export function AdminUsersScreen() {
  const { accessToken } = useAuthSession();

  const [query, setQuery] = useState("");
  const [debouncedQuery, setDebouncedQuery] = useState("");
  const [page, setPage] = useState(1);
  const [result, setResult] = useState<PaginatedAdminUsers | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState<PendingAction | null>(null);
  const [workingId, setWorkingId] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
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
          await fetchAdminUsers(accessToken, {
            query: debouncedQuery || undefined,
            page,
          }),
        );
      } catch (loadError) {
        if (loadError instanceof ApiError && loadError.status === 403) {
          setError("Non hai i permessi per consultare gli utenti.");
        } else {
          setError(getApiErrorMessage(loadError, "Impossibile caricare gli utenti."));
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

  async function confirmAction() {
    if (!pending) {
      return;
    }
    if (!accessToken) {
      setError("Sessione non disponibile. Accedi di nuovo.");
      setPending(null);
      return;
    }
    setWorkingId(pending.user.id);
    setError(null);
    setSuccess(null);
    try {
      const updated =
        pending.kind === "promote"
          ? await promoteOperator(accessToken, pending.user.id)
          : await revokeOperator(accessToken, pending.user.id);
      setSuccess(
        pending.kind === "promote"
          ? `${updated.displayName} è ora operatore.`
          : `${updated.displayName} non è più operatore.`,
      );
      setResult((current) =>
        current
          ? {
              ...current,
              items: current.items.map((row) => (row.id === updated.id ? updated : row)),
            }
          : current,
      );
    } catch (actionError) {
      if (actionError instanceof ApiError && actionError.code === "last_operator") {
        setError("Non puoi revocare l'ultimo operatore rimasto sulla piattaforma.");
      } else if (actionError instanceof ApiError && actionError.status === 403) {
        setError("Non hai i permessi per modificare questo utente.");
      } else {
        setError(getApiErrorMessage(actionError, "Impossibile completare l'operazione."));
      }
    } finally {
      setWorkingId(null);
      setPending(null);
    }
  }

  return (
    <PageContainer
      title="Utenti"
      testID="screen-admin-users"
      refreshing={refreshing}
      onRefresh={onRefresh}
    >
      <TextInput
        style={styles.input}
        value={query}
        onChangeText={setQuery}
        placeholder="Cerca per email o nome"
        autoCapitalize="none"
        autoCorrect={false}
        testID="admin-users-query"
      />

      {success ? (
        <UiStatePanel
          state="success"
          title="Operazione completata"
          message={success}
          testID="admin-users-success"
        />
      ) : null}
      {loading ? (
        <UiStatePanel
          state="loading"
          title="Caricamento utenti"
          message="Ricerca utenti in corso…"
          testID="admin-users-loading"
        />
      ) : null}
      {!loading && error ? (
        <UiStatePanel
          state={error.includes("permessi") ? "forbidden" : "error"}
          title="Utenti non disponibili"
          message={error}
          testID="admin-users-error"
        />
      ) : null}
      {!loading && !error && result?.items.length === 0 ? (
        <UiStatePanel
          state="empty"
          title="Nessun utente trovato"
          message="Modifica la ricerca o riprova più tardi."
          testID="admin-users-empty"
        />
      ) : null}
      {!loading && !error && result && result.items.length > 0 ? (
        <View testID="admin-users-list">
          {result.items.map((row) => (
            <View key={row.id} style={styles.listRow} testID={`admin-user-${row.id}`}>
              <View style={styles.identityRow}>
                <View>
                  <Text style={styles.name}>{row.displayName}</Text>
                  <Text style={styles.meta}>{row.email}</Text>
                </View>
                <Text style={styles.meta}>
                  {row.platformRole === "operator" ? "Operatore" : "Utente"}
                </Text>
              </View>
              {row.platformRole === "operator" ? (
                <Pressable
                  style={[styles.secondaryButton, workingId === row.id && styles.disabled]}
                  disabled={workingId === row.id}
                  onPress={() => setPending({ user: row, kind: "revoke" })}
                  testID={`admin-user-revoke-${row.id}`}
                >
                  <Text style={styles.secondaryButtonLabel}>Revoca operator</Text>
                </Pressable>
              ) : (
                <Pressable
                  style={[styles.button, workingId === row.id && styles.disabled]}
                  disabled={workingId === row.id}
                  onPress={() => setPending({ user: row, kind: "promote" })}
                  testID={`admin-user-promote-${row.id}`}
                >
                  <Text style={styles.buttonLabel}>Promuovi a operator</Text>
                </Pressable>
              )}
            </View>
          ))}
          {result.totalPages > 1 ? (
            <View style={styles.rowActions}>
              <Pressable
                style={[styles.secondaryButton, page <= 1 && styles.disabled]}
                disabled={page <= 1}
                onPress={() => setPage((current) => Math.max(1, current - 1))}
                testID="admin-users-prev-page"
              >
                <Text style={styles.secondaryButtonLabel}>Pagina precedente</Text>
              </Pressable>
              <Text style={styles.meta}>
                Pagina {result.page} di {result.totalPages} ({result.total} utenti)
              </Text>
              <Pressable
                style={[styles.secondaryButton, page >= result.totalPages && styles.disabled]}
                disabled={page >= result.totalPages}
                onPress={() => setPage((current) => Math.min(result.totalPages, current + 1))}
                testID="admin-users-next-page"
              >
                <Text style={styles.secondaryButtonLabel}>Pagina successiva</Text>
              </Pressable>
            </View>
          ) : null}
        </View>
      ) : null}

      {pending ? (
        <View style={styles.confirmBox} testID="admin-user-confirm-box">
          <Text style={styles.sectionTitle}>
            {pending.kind === "promote" ? "Promuovi a operator" : "Revoca operator"}
          </Text>
          <Text style={styles.meta}>
            {pending.kind === "promote"
              ? `Confermi di voler promuovere ${pending.user.displayName} a operatore globale? Otterrà accesso al pannello /admin.`
              : `Confermi di voler revocare il ruolo di operatore a ${pending.user.displayName}?`}
          </Text>
          <View style={styles.rowActions}>
            <Pressable
              style={styles.secondaryButton}
              onPress={() => setPending(null)}
              testID="admin-user-confirm-cancel"
            >
              <Text style={styles.secondaryButtonLabel}>Annulla</Text>
            </Pressable>
            <Pressable
              style={styles.button}
              onPress={() => void confirmAction()}
              testID="admin-user-confirm"
            >
              <Text style={styles.buttonLabel}>Conferma</Text>
            </Pressable>
          </View>
        </View>
      ) : null}
    </PageContainer>
  );
}
