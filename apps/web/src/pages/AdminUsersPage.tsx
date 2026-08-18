import type { AdminUser, PaginatedAdminUsers } from "@fantappero/contracts";
import { Breadcrumb, Button, Input, Modal, PageContainer, UiStatePanel } from "@fantappero/ui";
import { useCallback, useEffect, useState } from "react";
import { fetchAdminUsers, promoteOperator, revokeOperator } from "../api/admin";
import { ApiError } from "../api/client";
import { getApiErrorMessage } from "../auth/AuthContext";
import { loadStoredSession } from "../auth/sessionStorage";

type PendingAction = { user: AdminUser; kind: "promote" | "revoke" };

export function AdminUsersPage() {
  const [query, setQuery] = useState("");
  const [debouncedQuery, setDebouncedQuery] = useState("");
  const [page, setPage] = useState(1);
  const [result, setResult] = useState<PaginatedAdminUsers | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState<PendingAction | null>(null);
  const [workingId, setWorkingId] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

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
              <span>{row.platformRole === "operator" ? "Operatore" : "Utente"}</span>
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
            </li>
          ))}
        </ul>
      ) : null}

      <Modal
        open={pending !== null}
        onClose={() => setPending(null)}
        title={pending?.kind === "promote" ? "Promuovi a operator" : "Revoca operator"}
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
            : `Confermi di voler revocare il ruolo di operatore a ${pending?.user.displayName}?`}
        </p>
      </Modal>
    </PageContainer>
  );
}
