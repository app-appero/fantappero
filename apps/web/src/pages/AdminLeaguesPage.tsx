import type { LeagueState, PaginatedAdminLeagues } from "@fantappero/contracts";
import { Breadcrumb, Button, Input, PageContainer, UiStatePanel } from "@fantappero/ui";
import { useCallback, useEffect, useState } from "react";
import { deleteAdminLeague, fetchAdminLeagues } from "../api/admin";
import { ApiError } from "../api/client";
import { getApiErrorMessage } from "../auth/AuthContext";
import { loadStoredSession } from "../auth/sessionStorage";
import { leagueStateLabel } from "../leagues/leagueLabels";

export function AdminLeaguesPage() {
  const [query, setQuery] = useState("");
  const [debouncedQuery, setDebouncedQuery] = useState("");
  const [page, setPage] = useState(1);
  const [result, setResult] = useState<PaginatedAdminLeagues | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

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
        await fetchAdminLeagues(session.accessToken, {
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
  }, [debouncedQuery, page]);

  const [pendingDelete, setPendingDelete] = useState<{ id: string; name: string } | null>(null);
  const [deleting, setDeleting] = useState(false);
  const [actionMessage, setActionMessage] = useState<string | null>(null);

  const confirmDelete = useCallback(async () => {
    if (!pendingDelete) {
      return;
    }
    const session = loadStoredSession();
    if (!session?.accessToken) {
      setActionMessage("Sessione non disponibile. Accedi di nuovo.");
      return;
    }
    setDeleting(true);
    setActionMessage(null);
    try {
      await deleteAdminLeague(session.accessToken, pendingDelete.id);
      setActionMessage(`Lega "${pendingDelete.name}" eliminata. Gli allenatori sono stati avvisati.`);
      setPendingDelete(null);
      await load();
    } catch (deleteError) {
      setActionMessage(getApiErrorMessage(deleteError, "Impossibile eliminare la lega."));
    } finally {
      setDeleting(false);
    }
  }, [pendingDelete, load]);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <PageContainer
      title="Leghe"
      header={
        <Breadcrumb items={[{ label: "Operazioni", href: "/admin" }, { label: "Leghe" }]} />
      }
    >
      <Input
        label="Cerca per nome lega"
        name="admin-leagues-query"
        value={query}
        onChange={(event) => setQuery(event.target.value)}
      />

      {actionMessage ? (
        <p role="status" data-testid="admin-leagues-action-message">
          {actionMessage}
        </p>
      ) : null}
      {pendingDelete ? (
        <div role="alertdialog" aria-label="Conferma eliminazione lega" data-testid="admin-leagues-confirm">
          <p>
            Eliminare definitivamente la lega &quot;{pendingDelete.name}&quot;? Gli allenatori
            riceveranno una notifica. L&apos;azione non è reversibile.
          </p>
          <Button variant="danger" size="sm" disabled={deleting} onClick={() => void confirmDelete()}>
            {deleting ? "Eliminazione…" : "Conferma eliminazione"}
          </Button>{" "}
          <Button variant="secondary" size="sm" disabled={deleting} onClick={() => setPendingDelete(null)}>
            Annulla
          </Button>
        </div>
      ) : null}

      {loading ? (
        <UiStatePanel
          state="loading"
          title="Caricamento leghe"
          message="Ricerca leghe in corso…"
          testId="admin-leagues-loading"
        />
      ) : null}
      {!loading && error ? (
        <UiStatePanel
          state={error.includes("permessi") ? "forbidden" : "error"}
          title="Leghe non disponibili"
          message={error}
          testId="admin-leagues-error"
        />
      ) : null}
      {!loading && !error && result?.items.length === 0 ? (
        <UiStatePanel
          state="empty"
          title="Nessuna lega trovata"
          message="Modifica la ricerca o riprova più tardi."
          testId="admin-leagues-empty"
        />
      ) : null}
      {!loading && !error && result && result.items.length > 0 ? (
        <ul className="fa-admin-leagues__list" data-testid="admin-leagues-list">
          {result.items.map((league) => (
            <li key={league.id} className="fa-admin-leagues__item">
              <strong className="fa-admin-leagues__name">{league.name}</strong>
              <span className="fa-admin-leagues__state">{leagueStateLabel(league.state as LeagueState)}</span>
              <span className="fa-admin-leagues__owner">Admin: {league.ownerDisplayName ?? "—"}</span>
              <Button
                variant="danger"
                size="sm"
                onClick={() => {
                  setActionMessage(null);
                  setPendingDelete({ id: league.id, name: league.name });
                }}
              >
                Elimina
              </Button>
            </li>
          ))}
        </ul>
      ) : null}
      {/* L'API restituisce 20 leghe per pagina: senza pager si vedevano solo le prime. */}
      {!loading && !error && result && result.totalPages > 1 ? (
        <div className="fa-feedback-admin__pager" data-testid="admin-leagues-pager">
          <Button
            type="button"
            variant="secondary"
            disabled={page <= 1}
            onClick={() => setPage((value) => Math.max(1, value - 1))}
            data-testid="admin-leagues-prev-page"
          >
            Precedente
          </Button>
          <span>
            Pagina {result.page} di {result.totalPages} · {result.total} leghe
          </span>
          <Button
            type="button"
            variant="secondary"
            disabled={page >= result.totalPages}
            onClick={() => setPage((value) => Math.min(result.totalPages, value + 1))}
            data-testid="admin-leagues-next-page"
          >
            Successiva
          </Button>
        </div>
      ) : null}
    </PageContainer>
  );
}
