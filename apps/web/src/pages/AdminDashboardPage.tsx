import type { AdminOverview } from "@fantappero/contracts";
import { Breadcrumb, PageContainer, UiStatePanel } from "@fantappero/ui";
import { useCallback, useEffect, useState } from "react";
import { fetchAdminOverview } from "../api/admin";
import { ApiError } from "../api/client";
import { getApiErrorMessage } from "../auth/AuthContext";
import { loadStoredSession } from "../auth/sessionStorage";

export function AdminDashboardPage() {
  const [overview, setOverview] = useState<AdminOverview | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

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
      setOverview(await fetchAdminOverview(session.accessToken));
    } catch (loadError) {
      if (loadError instanceof ApiError && loadError.status === 403) {
        setError("Non hai i permessi per consultare il pannello operatore.");
      } else {
        setError(getApiErrorMessage(loadError, "Impossibile caricare il pannello operatore."));
      }
      setOverview(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <PageContainer
      title="Pannello operatore"
      header={<Breadcrumb items={[{ label: "Operazioni" }]} />}
    >
      {loading ? (
        <UiStatePanel
          state="loading"
          title="Caricamento"
          message="Recupero i dati del pannello operatore…"
          testId="admin-dashboard-loading"
        />
      ) : null}
      {!loading && error ? (
        <UiStatePanel
          state={error.includes("permessi") ? "forbidden" : "error"}
          title="Pannello non disponibile"
          message={error}
          testId="admin-dashboard-error"
        />
      ) : null}
      {!loading && !error && overview ? (
        <div className="fa-admin-overview" data-testid="admin-dashboard-success">
          <section aria-labelledby="admin-overview-identity">
            <h2 id="admin-overview-identity">Identità operatore</h2>
            <p data-testid="admin-overview-name">{overview.operatorDisplayName}</p>
            <p>
              Ambiente:{" "}
              <strong data-testid="admin-overview-environment">{overview.environment}</strong>
            </p>
          </section>
          <section aria-labelledby="admin-overview-counts">
            <h2 id="admin-overview-counts">Conteggi piattaforma</h2>
            <ul>
              <li>Utenti registrati: {overview.usersCount}</li>
              <li>Operatori: {overview.operatorsCount}</li>
              <li>Leghe: {overview.leaguesCount}</li>
            </ul>
          </section>
        </div>
      ) : null}
      {!loading && !error && !overview ? (
        <UiStatePanel
          state="empty"
          title="Nessun dato disponibile"
          message="Non è stato possibile calcolare i conteggi piattaforma."
          testId="admin-dashboard-empty"
        />
      ) : null}
    </PageContainer>
  );
}
