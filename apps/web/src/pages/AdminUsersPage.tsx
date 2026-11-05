import type { AdminTestMode, AdminUser, PaginatedAdminUsers } from "@fantappero/contracts";
import { Badge, Breadcrumb, Button, Input, Modal, PageContainer, UiStatePanel } from "@fantappero/ui";
import { useCallback, useEffect, useState } from "react";
import {
  addTester,
  fetchAdminUsers,
  fetchTestMode,
  impersonateUser,
  promoteOperator,
  removeTester,
  revokeOperator,
  setTestMode,
} from "../api/admin";
import { ApiError } from "../api/client";
import { getApiErrorMessage, useAuth } from "../auth/AuthContext";
import { loadStoredSession } from "../auth/sessionStorage";
import { useNavigate } from "../router/simpleRouter";

type PendingAction = { user: AdminUser; kind: "promote" | "revoke" | "impersonate" };

export function AdminUsersPage() {
  const { startImpersonation } = useAuth();
  const navigate = useNavigate();
  const [query, setQuery] = useState("");
  const [debouncedQuery, setDebouncedQuery] = useState("");
  const [page, setPage] = useState(1);
  const [result, setResult] = useState<PaginatedAdminUsers | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState<PendingAction | null>(null);
  const [workingId, setWorkingId] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [testMode, setTestModeState] = useState<AdminTestMode | null>(null);
  const [testModeBusy, setTestModeBusy] = useState(false);
  const [newTesterEmail, setNewTesterEmail] = useState("");

  useEffect(() => {
    const session = loadStoredSession();
    if (!session?.accessToken) {
      return;
    }
    void fetchTestMode(session.accessToken)
      .then(setTestModeState)
      .catch(() => setTestModeState(null));
  }, []);

  /** Esegue una modifica alla modalità test e aggiorna stato e messaggi. */
  async function runTestModeAction(
    action: (token: string) => Promise<AdminTestMode>,
    message: string,
    refreshUsers = false,
  ) {
    const session = loadStoredSession();
    if (!session?.accessToken) {
      setError("Sessione non disponibile. Accedi di nuovo.");
      return;
    }
    setTestModeBusy(true);
    setError(null);
    setSuccess(null);
    try {
      setTestModeState(await action(session.accessToken));
      setSuccess(message);
      if (refreshUsers) {
        await load();
      }
    } catch (actionError) {
      setError(getApiErrorMessage(actionError, "Operazione sulla modalità test non riuscita."));
    } finally {
      setTestModeBusy(false);
    }
  }

  useEffect(() => {
    const timer = window.setTimeout(() => {
      setPage(1);
      setDebouncedQuery(query.trim());
    }, 300);
    return () => window.clearTimeout(timer);
  }, [query]);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    const session = loadStoredSession();
    if (!session?.accessToken) {
      setError("Sessione non disponibile. Accedi di nuovo.");
      setLoading(false);
      return;
    }
    try {
      setResult(
        await fetchAdminUsers(session.accessToken, {
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
  }, [debouncedQuery, page]);

  useEffect(() => {
    void load();
  }, [load]);

  async function confirmAction() {
    if (!pending) {
      return;
    }
    const session = loadStoredSession();
    if (!session?.accessToken) {
      setError("Sessione non disponibile. Accedi di nuovo.");
      setPending(null);
      return;
    }
    setWorkingId(pending.user.id);
    setError(null);
    setSuccess(null);
    try {
      if (pending.kind === "impersonate") {
        const result = await impersonateUser(session.accessToken, pending.user.id);
        await startImpersonation(result);
        navigate("/leghe");
        return;
      }
      const updated =
        pending.kind === "promote"
          ? await promoteOperator(session.accessToken, pending.user.id)
          : await revokeOperator(session.accessToken, pending.user.id);
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
      header={
        <Breadcrumb items={[{ label: "Operazioni", href: "/admin" }, { label: "Utenti" }]} />
      }
    >
      <section className="fa-admin-testmode" data-testid="admin-testmode">
        <h2>Modalità test</h2>
        {testMode ? (
          <>
            <p>
              {testMode.enabled
                ? "Attiva: possono accedere solo i tester e gli operatori. Gli altri vedono «Non autorizzato»."
                : "Spenta: chiunque abbia il link può accedere con Google."}
            </p>
            <Button
              type="button"
              variant={testMode.enabled ? "secondary" : "primary"}
              loading={testModeBusy}
              onClick={() =>
                void runTestModeAction(
                  (token) => setTestMode(token, !testMode.enabled),
                  testMode.enabled ? "Modalità test disattivata." : "Modalità test attivata.",
                )
              }
              data-testid="admin-testmode-toggle"
            >
              {testMode.enabled ? "Disattiva modalità test" : "Attiva modalità test"}
            </Button>
            <form
              className="fa-admin-testmode__add"
              onSubmit={(event) => {
                event.preventDefault();
                const email = newTesterEmail.trim();
                if (!email) {
                  return;
                }
                void runTestModeAction(
                  (token) => addTester(token, email),
                  `${email} è ora tester.`,
                  true,
                ).then(() => setNewTesterEmail(""));
              }}
            >
              <Input
                label="Aggiungi un tester (email Google)"
                name="admin-tester-email"
                type="email"
                value={newTesterEmail}
                onChange={(event) => setNewTesterEmail(event.target.value)}
              />
              <Button type="submit" variant="primary" loading={testModeBusy} data-testid="admin-tester-add">
                Aggiungi
              </Button>
            </form>
            {testMode.testers.length === 0 ? (
              <p data-testid="admin-testers-empty">Nessun tester in lista (gli operatori sono sempre abilitati).</p>
            ) : (
              <ul className="fa-admin-users__list" data-testid="admin-testers-list">
                {testMode.testers.map((tester) => (
                  <li key={tester.id} className="fa-admin-users__item">
                    <span className="fa-admin-users__identity">
                      <strong>{tester.displayName ?? "Non ha ancora acceduto"}</strong>
                      <small>{tester.email}</small>
                    </span>
                    <span className="fa-admin-users__actions">
                      <Button
                        type="button"
                        size="sm"
                        variant="ghost"
                        loading={testModeBusy}
                        onClick={() =>
                          void runTestModeAction(
                            (token) => removeTester(token, tester.id),
                            `${tester.email} non è più tester.`,
                            true,
                          )
                        }
                        data-testid={`admin-tester-remove-${tester.id}`}
                      >
                        Rimuovi
                      </Button>
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </>
        ) : (
          <p>Stato della modalità test non disponibile.</p>
        )}
      </section>

      <Input
        label="Cerca per email o nome"
        name="admin-users-query"
        value={query}
        onChange={(event) => setQuery(event.target.value)}
      />

      {success ? (
        <UiStatePanel
          state="success"
          title="Operazione completata"
          message={success}
          testId="admin-users-success"
        />
      ) : null}
      {loading ? (
        <UiStatePanel
          state="loading"
          title="Caricamento utenti"
          message="Ricerca utenti in corso…"
          testId="admin-users-loading"
        />
      ) : null}
      {!loading && error ? (
        <UiStatePanel
          state={error.includes("permessi") ? "forbidden" : "error"}
          title="Utenti non disponibili"
          message={error}
          testId="admin-users-error"
        />
      ) : null}
      {!loading && !error && result?.items.length === 0 ? (
        <UiStatePanel
          state="empty"
          title="Nessun utente trovato"
          message="Modifica la ricerca o riprova più tardi."
          testId="admin-users-empty"
        />
      ) : null}
      {!loading && !error && result && result.items.length > 0 ? (
        <ul className="fa-admin-users__list" data-testid="admin-users-list">
          {result.items.map((row) => (
            <li key={row.id} className="fa-admin-users__item">
              <span className="fa-admin-users__identity">
                <strong>{row.displayName}</strong>
                <small>{row.email}</small>
              </span>
              <Badge
                variant={row.platformRole === "operator" ? "accent" : "neutral"}
                className="fa-admin-users__role"
              >
                {row.platformRole === "operator" ? "Operatore" : "Utente"}
              </Badge>
              {row.isTester ? (
                <Badge variant="success" data-testid={`admin-user-tester-badge-${row.id}`}>
                  Tester
                </Badge>
              ) : null}
              <span className="fa-admin-users__actions">
                {row.platformRole !== "operator" ? (
                  <Button
                    type="button"
                    size="sm"
                    variant={row.isTester ? "secondary" : "primary"}
                    loading={testModeBusy}
                    onClick={() => {
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
                    data-testid={`admin-user-tester-${row.id}`}
                  >
                    {row.isTester ? "Revoca tester" : "Abilita tester"}
                  </Button>
                ) : null}
                <Button
                  type="button"
                  size="sm"
                  variant="ghost"
                  loading={workingId === row.id}
                  onClick={() => setPending({ user: row, kind: "impersonate" })}
                  data-testid={`admin-user-impersonate-${row.id}`}
                >
                  Impersona
                </Button>
                {row.platformRole === "operator" ? (
                  <Button
                    type="button"
                    size="sm"
                    variant="secondary"
                    loading={workingId === row.id}
                    onClick={() => setPending({ user: row, kind: "revoke" })}
                    data-testid={`admin-user-revoke-${row.id}`}
                  >
                    Revoca operator
                  </Button>
                ) : (
                  <Button
                    type="button"
                    size="sm"
                    variant="primary"
                    loading={workingId === row.id}
                    onClick={() => setPending({ user: row, kind: "promote" })}
                    data-testid={`admin-user-promote-${row.id}`}
                  >
                    Promuovi a operator
                  </Button>
                )}
              </span>
            </li>
          ))}
        </ul>
      ) : null}

      <Modal
        open={pending !== null}
        onClose={() => setPending(null)}
        title={
          pending?.kind === "promote"
            ? "Promuovi a operator"
            : pending?.kind === "impersonate"
              ? "Impersona utente"
              : "Revoca operator"
        }
        footer={
          <>
            <Button type="button" variant="ghost" onClick={() => setPending(null)}>
              Annulla
            </Button>
            <Button
              type="button"
              variant="primary"
              onClick={() => void confirmAction()}
              data-testid="admin-user-confirm"
            >
              Conferma
            </Button>
          </>
        }
      >
        <p>
          {pending?.kind === "promote"
            ? `Confermi di voler promuovere ${pending.user.displayName} a operatore globale? Otterrà accesso al pannello /admin.`
            : pending?.kind === "impersonate"
              ? `Accederai come ${pending.user.displayName} per qualche minuto, a scopo di assistenza. L'operazione viene registrata nell'audit log.`
              : `Confermi di voler revocare il ruolo di operatore a ${pending?.user.displayName}?`}
        </p>
      </Modal>
    </PageContainer>
  );
}
