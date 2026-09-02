import type { PaginatedAdminLeagues } from "@fantappero/contracts";
import { Breadcrumb, Input, PageContainer, UiStatePanel } from "@fantappero/ui";
import { useCallback, useEffect, useState } from "react";
import { fetchAdminLeagues } from "../api/admin";
import { ApiError } from "../api/client";
import { getApiErrorMessage } from "../auth/AuthContext";
import { loadStoredSession } from "../auth/sessionStorage";

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
              <strong>{league.name}</strong>
              <span>{league.state}</span>
              <span>{league.ownerDisplayName ?? "—"}</span>
            </li>
          ))}
        </ul>
      ) : null}
    </PageContainer>
  );
}
