import type { AdminOverview } from "@fantappero/contracts";
import { Breadcrumb, PageContainer, UiStatePanel } from "@fantappero/ui";
import { useCallback, useEffect, useState } from "react";
import { fetchAdminOverview } from "../api/admin";
import { ApiError } from "../api/client";
import { getApiErrorMessage } from "../auth/AuthContext";
import { loadStoredSession } from "../auth/sessionStorage";
import { Link } from "../router/simpleRouter";

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
          <section className="fa-admin-overview__hero" aria-labelledby="admin-overview-identity">
            <div>
              <h2 id="admin-overview-identity" className="fa-admin-overview__label">
                Identità operatore
              </h2>
              <p className="fa-admin-overview__name" data-testid="admin-overview-name">
                {overview.operatorDisplayName}
              </p>
            </div>
            <p className="fa-admin-overview__env">
              Ambiente:{" "}
              <strong data-testid="admin-overview-environment">{overview.environment}</strong>
            </p>
          </section>
          <section aria-labelledby="admin-overview-counts">
            <h2 id="admin-overview-counts" className="fa-sr-only">
              Conteggi piattaforma
            </h2>
            <ul className="fa-admin-overview__tiles">
              <li>
                <span className="fa-admin-overview__label">Utenti registrati</span>
                <strong>{overview.usersCount}</strong>
              </li>
              <li>
                <span className="fa-admin-overview__label">Operatori</span>
                <strong>{overview.operatorsCount}</strong>
              </li>
              <li>
                <span className="fa-admin-overview__label">Leghe</span>
                <strong>{overview.leaguesCount}</strong>
              </li>
            </ul>
          </section>
          <nav className="fa-admin-overview__links" aria-label="Sezioni operatore">
            <Link to="/admin/utenti">
              <strong>Utenti</strong>
              <span>Promuovi, revoca, impersona</span>
            </Link>
            <Link to="/admin/leghe">
              <strong>Leghe globali</strong>
              <span>Tutte le leghe della piattaforma</span>
            </Link>
            <Link to="/admin/listone">
              <strong>Listone</strong>
              <span>Aggiorna il listone dal provider</span>
            </Link>
            <Link to="/admin/turni">
              <strong>Turni</strong>
              <span>Sincronizza, calcola, apri</span>
            </Link>
            <Link to="/admin/job">
              <strong>Job automatici</strong>
              <span>Accendi, spegni, cambia la frequenza</span>
            </Link>
            <Link to="/admin/email">
              <strong>Email</strong>
              <span>Scrivi e invia email dal portale</span>
            </Link>
            <Link to="/admin/notifiche">
              <strong>Notifiche</strong>
              <span>Avvisi, novità e prove agli utenti</span>
            </Link>
          </nav>
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
