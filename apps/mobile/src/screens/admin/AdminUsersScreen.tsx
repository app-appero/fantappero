import type {
  AdminBlocklist,
  AdminTestMode,
  AdminUser,
  PaginatedAdminUsers,
} from "@fantappero/contracts";
import { useNavigation } from "@react-navigation/core";
import type { NativeStackNavigationProp } from "@react-navigation/native-stack";
import { useCallback, useEffect, useState } from "react";
import { Modal, Pressable, Text, View } from "react-native";
import { AppTextInput as TextInput } from "../../components/AppTextInput";
import {
  addBlocked,
  addTester,
  deleteUser,
  fetchAdminUsers,
  fetchBlocklist,
  fetchTestMode,
  impersonateUser,
  promoteOperator,
  removeBlocked,
  removeTester,
  revokeOperator,
  setTestMode,
} from "../../api/admin";
import { ApiError } from "../../api/client";
import { adminUiStyles as styles } from "../../admin/adminUiStyles";
import { ScreenTabs } from "../../components/ScreenTabs";
import { UiStatePanel } from "../../components/UiStatePanel";
import { PageContainer } from "../../layout/PageContainer";
import { leaveAdminForApp } from "../../navigation/adminEntry";
import type { RootStackParamList } from "../../navigation/types";
import { getApiErrorMessage, useAuthSession } from "../../session/DemoSessionContext";

type PendingAction = {
  user: AdminUser;
  kind: "promote" | "revoke" | "impersonate" | "delete";
};

const USERS_TABS = [
  { id: "utenti", label: "Utenti" },
  { id: "lista-nera", label: "Lista nera" },
] as const;

/** Elenco utenti + promuovi/revoca operatore — mobile port of `apps/web/src/pages/AdminUsersPage.tsx` (EP11-04b). */
export function AdminUsersScreen() {
  const navigation = useNavigation<NativeStackNavigationProp<RootStackParamList>>();
  const { accessToken, startImpersonation } = useAuthSession();

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
  const [testMode, setTestModeState] = useState<AdminTestMode | null>(null);
  const [testModeBusy, setTestModeBusy] = useState(false);
  const [newTesterEmail, setNewTesterEmail] = useState("");
  const [tab, setTab] = useState<"utenti" | "lista-nera">("utenti");
  const [blocklist, setBlocklist] = useState<AdminBlocklist | null>(null);
  const [blockEmail, setBlockEmail] = useState("");
  const [blockReason, setBlockReason] = useState("");
  const [blockBusy, setBlockBusy] = useState(false);

  useEffect(() => {
    if (!accessToken) {
      return;
    }
    void fetchTestMode(accessToken)
      .then(setTestModeState)
      .catch(() => setTestModeState(null));
    void fetchBlocklist(accessToken)
      .then(setBlocklist)
      .catch(() => setBlocklist(null));
  }, [accessToken]);

  /** Modifica alla lista nera (aggiungi/rimuovi) con messaggi di esito. */
  async function runBlocklistAction(
    action: (token: string) => Promise<AdminBlocklist>,
    message: string,
  ): Promise<boolean> {
    if (!accessToken) {
      setError("Sessione non disponibile. Accedi di nuovo.");
      return false;
    }
    setBlockBusy(true);
    setError(null);
    setSuccess(null);
    try {
      setBlocklist(await action(accessToken));
      setSuccess(message);
      return true;
    } catch (actionError) {
      setError(getApiErrorMessage(actionError, "Operazione sulla lista nera non riuscita."));
      return false;
    } finally {
      setBlockBusy(false);
    }
  }

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

  /** Esegue una modifica alla modalità test e aggiorna stato e messaggi. */
  async function runTestModeAction(
    action: (token: string) => Promise<AdminTestMode>,
    message: string,
    refreshUsers = false,
  ) {
    if (!accessToken) {
      setError("Sessione non disponibile. Accedi di nuovo.");
      return;
    }
    setTestModeBusy(true);
    setError(null);
    setSuccess(null);
    try {
      setTestModeState(await action(accessToken));
      setSuccess(message);
      if (refreshUsers) {
        await load({ silent: true });
      }
    } catch (actionError) {
      setError(getApiErrorMessage(actionError, "Operazione sulla modalità test non riuscita."));
    } finally {
      setTestModeBusy(false);
    }
  }

  async function confirmAction(block = true) {
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
      if (pending.kind === "impersonate") {
        const result = await impersonateUser(accessToken, pending.user.id);
        await startImpersonation(result);
        setPending(null);
        leaveAdminForApp();
        navigation.getParent()?.navigate("MainTabs");
        return;
      }
      if (pending.kind === "delete") {
        const deleted = await deleteUser(accessToken, pending.user.id, block);
        setSuccess(
          deleted.blockedEmail
            ? `${pending.user.displayName} è stato eliminato e ${deleted.blockedEmail} è in lista nera.`
            : `${pending.user.displayName} è stato eliminato.`,
        );
        setBlocklist(await fetchBlocklist(accessToken));
        await load({ silent: true });
        return;
      }
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
      } else if (actionError instanceof ApiError && actionError.code === "protected_operator") {
        setError("Questo operatore è protetto: non può essere declassato, eliminato o bloccato.");
      } else if (
        actionError instanceof ApiError &&
        actionError.code === "operator_must_be_revoked_first"
      ) {
        setError("Per eliminare o bloccare un operatore revoca prima il suo ruolo.");
      } else if (actionError instanceof ApiError && actionError.code === "cannot_impersonate_self") {
        setError("Non puoi impersonare te stesso.");
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
      <ScreenTabs
        items={USERS_TABS}
        activeId={tab}
        onSelect={(id) => setTab(id as "utenti" | "lista-nera")}
        testID="admin-users-tabs"
      />

      {tab === "lista-nera" ? (
        <>
      <View style={styles.listRow} testID="admin-blocklist">
        <Text style={styles.sectionTitle}>Lista nera</Text>
        <Text style={styles.meta}>
          Chi è in lista nera non può accedere né registrarsi di nuovo. Gli utenti eliminati
          dall&apos;operatore finiscono qui in automatico.
        </Text>
        <TextInput
          style={styles.input}
          value={blockEmail}
          onChangeText={setBlockEmail}
          placeholder="Email da bloccare"
          autoCapitalize="none"
          autoCorrect={false}
          keyboardType="email-address"
          testID="admin-block-email"
        />
        <TextInput
          style={styles.input}
          value={blockReason}
          onChangeText={setBlockReason}
          placeholder="Motivo (facoltativo)"
          testID="admin-block-reason"
        />
        <Pressable
          style={[styles.button, blockBusy && styles.disabled]}
          disabled={blockBusy || !blockEmail.trim()}
          onPress={() => {
            const email = blockEmail.trim();
            void runBlocklistAction(
              (token) => addBlocked(token, email, blockReason.trim()),
              `${email} è stato aggiunto alla lista nera.`,
            ).then((ok) => {
              if (ok) {
                setBlockEmail("");
                setBlockReason("");
              }
            });
          }}
          testID="admin-block-add"
        >
          <Text style={styles.buttonLabel}>Aggiungi alla lista nera</Text>
        </Pressable>
        {blocklist === null ? (
          <Text style={styles.meta}>Lista nera non disponibile.</Text>
        ) : blocklist.items.length === 0 ? (
          <Text style={styles.meta} testID="admin-blocklist-empty">
            La lista nera è vuota.
          </Text>
        ) : (
          blocklist.items.map((entry) => (
            <View key={entry.id} style={styles.identityRow} testID={`admin-blocked-${entry.id}`}>
              <View style={{ flex: 1 }}>
                <Text style={styles.name}>{entry.email}</Text>
                <Text style={styles.meta}>
                  {new Date(entry.createdAt).toLocaleDateString("it-IT")}
                  {entry.reason ? ` · ${entry.reason}` : ""}
                </Text>
              </View>
              <Pressable
                style={[styles.secondaryButton, blockBusy && styles.disabled]}
                disabled={blockBusy}
                onPress={() =>
                  void runBlocklistAction(
                    (token) => removeBlocked(token, entry.id),
                    `${entry.email} è stato tolto dalla lista nera.`,
                  )
                }
                testID={`admin-block-remove-${entry.id}`}
              >
                <Text style={styles.secondaryButtonLabel}>Togli</Text>
              </Pressable>
            </View>
          ))
        )}
      </View>
        </>
      ) : (
        <>
      <View style={styles.listRow} testID="admin-testmode">
        <Text style={styles.sectionTitle}>Modalità test</Text>
        {testMode ? (
          <>
            <Text style={styles.meta}>
              {testMode.enabled
                ? "Attiva: possono accedere solo i tester e gli operatori. Gli altri vedono «Non autorizzato»."
                : "Spenta: chiunque abbia il link può accedere con Google."}
            </Text>
            <Pressable
              style={[testMode.enabled ? styles.secondaryButton : styles.button, testModeBusy && styles.disabled]}
              disabled={testModeBusy}
              onPress={() =>
                void runTestModeAction(
                  (token) => setTestMode(token, !testMode.enabled),
                  testMode.enabled ? "Modalità test disattivata." : "Modalità test attivata.",
                )
              }
              testID="admin-testmode-toggle"
            >
              <Text style={testMode.enabled ? styles.secondaryButtonLabel : styles.buttonLabel}>
                {testMode.enabled ? "Disattiva modalità test" : "Attiva modalità test"}
              </Text>
            </Pressable>
            <TextInput
              style={styles.input}
              value={newTesterEmail}
              onChangeText={setNewTesterEmail}
              placeholder="Aggiungi un tester (email Google)"
              autoCapitalize="none"
              autoCorrect={false}
              keyboardType="email-address"
              testID="admin-tester-email"
            />
            <Pressable
              style={[styles.button, testModeBusy && styles.disabled]}
              disabled={testModeBusy || !newTesterEmail.trim()}
              onPress={() => {
                const email = newTesterEmail.trim();
                void runTestModeAction(
                  (token) => addTester(token, email),
                  `${email} è ora tester.`,
                  true,
                ).then(() => setNewTesterEmail(""));
              }}
              testID="admin-tester-add"
            >
              <Text style={styles.buttonLabel}>Aggiungi tester</Text>
            </Pressable>
            {testMode.testers.length === 0 ? (
              <Text style={styles.meta} testID="admin-testers-empty">
                Nessun tester in lista (gli operatori sono sempre abilitati).
              </Text>
            ) : (
              testMode.testers.map((tester) => (
                <View key={tester.id} style={styles.identityRow} testID={`admin-tester-${tester.id}`}>
                  <View style={{ flex: 1 }}>
                    <Text style={styles.name}>{tester.displayName ?? "Non ha ancora acceduto"}</Text>
                    <Text style={styles.meta}>{tester.email}</Text>
                  </View>
                  <Pressable
                    style={[styles.secondaryButton, testModeBusy && styles.disabled]}
                    disabled={testModeBusy}
                    onPress={() =>
                      void runTestModeAction(
                        (token) => removeTester(token, tester.id),
                        `${tester.email} non è più tester.`,
                        true,
                      )
                    }
                    testID={`admin-tester-remove-${tester.id}`}
                  >
                    <Text style={styles.secondaryButtonLabel}>Rimuovi</Text>
                  </Pressable>
                </View>
              ))
            )}
          </>
        ) : (
          <Text style={styles.meta}>Stato della modalità test non disponibile.</Text>
        )}
      </View>

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
                  {row.isTester ? " · Tester" : ""}
                </Text>
              </View>
              {row.platformRole !== "operator" ? (
                <Pressable
                  style={[row.isTester ? styles.secondaryButton : styles.button, testModeBusy && styles.disabled]}
                  disabled={testModeBusy}
                  onPress={() => {
                    const existing = testMode?.testers.find(
                      (tester) => tester.email.toLowerCase() === row.email.toLowerCase(),
                    );
                    if (row.isTester && existing) {
                      void runTestModeAction(
                        (token) => removeTester(token, existing.id),
                        `${row.displayName} non è più tester.`,
                        true,
                      );
                    } else if (!row.isTester) {
                      void runTestModeAction(
                        (token) => addTester(token, row.email),
                        `${row.displayName} è ora tester.`,
                        true,
                      );
                    }
                  }}
                  testID={`admin-user-tester-${row.id}`}
                >
                  <Text style={row.isTester ? styles.secondaryButtonLabel : styles.buttonLabel}>
                    {row.isTester ? "Revoca tester" : "Abilita tester"}
                  </Text>
                </Pressable>
              ) : null}
              <Pressable
                style={[styles.secondaryButton, workingId === row.id && styles.disabled]}
                disabled={workingId === row.id}
                onPress={() => setPending({ user: row, kind: "impersonate" })}
                testID={`admin-user-impersonate-${row.id}`}
              >
                <Text style={styles.secondaryButtonLabel}>Impersona</Text>
              </Pressable>
              {row.isProtected ? (
                <Text style={styles.meta} testID={`admin-user-protected-${row.id}`}>
                  Operatore protetto
                </Text>
              ) : row.platformRole === "operator" ? (
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
              {row.platformRole !== "operator" ? (
                <Pressable
                  style={[styles.secondaryButton, workingId === row.id && styles.disabled]}
                  disabled={workingId === row.id}
                  onPress={() => setPending({ user: row, kind: "delete" })}
                  testID={`admin-user-delete-${row.id}`}
                >
                  <Text style={styles.secondaryButtonLabel}>Elimina</Text>
                </Pressable>
              ) : null}
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

        </>
      )}

      <Modal
        visible={pending !== null}
        transparent
        animationType="fade"
        onRequestClose={() => setPending(null)}
      >
        <View style={styles.confirmOverlay}>
          {pending ? (
            <View style={styles.confirmBox} testID="admin-user-confirm-box">
              <Text style={styles.sectionTitle}>
                {pending.kind === "promote"
                  ? "Promuovi a operator"
                  : pending.kind === "impersonate"
                    ? "Impersona utente"
                    : pending.kind === "delete"
                      ? "Elimina utente"
                      : "Revoca operator"}
              </Text>
              <Text style={styles.meta}>
                {pending.kind === "promote"
                  ? `Confermi di voler promuovere ${pending.user.displayName} a operatore globale? Otterrà accesso al pannello /admin.`
                  : pending.kind === "impersonate"
                    ? `Accederai come ${pending.user.displayName} per qualche minuto, a scopo di assistenza.`
                    : pending.kind === "delete"
                      ? `Sei sicuro di voler eliminare ${pending.user.displayName} (${pending.user.email})? I suoi dati personali vengono rimossi. «Elimina» elimina e basta (potrà registrarsi di nuovo); «Elimina e lista nera» blocca anche l'indirizzo: non potrà più accedere né registrarsi.`
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
                {pending.kind === "delete" ? (
                  <>
                    <Pressable
                      style={styles.secondaryButton}
                      onPress={() => void confirmAction(false)}
                      testID="admin-user-delete-only"
                    >
                      <Text style={styles.secondaryButtonLabel}>Elimina</Text>
                    </Pressable>
                    <Pressable
                      style={styles.button}
                      onPress={() => void confirmAction(true)}
                      testID="admin-user-delete-and-block"
                    >
                      <Text style={styles.buttonLabel}>Elimina e lista nera</Text>
                    </Pressable>
                  </>
                ) : (
                  <Pressable
                    style={styles.button}
                    onPress={() => void confirmAction()}
                    testID="admin-user-confirm"
                  >
                    <Text style={styles.buttonLabel}>Conferma</Text>
                  </Pressable>
                )}
              </View>
            </View>
          ) : null}
        </View>
      </Modal>
    </PageContainer>
  );
}
