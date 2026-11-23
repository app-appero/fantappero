import {
  buildOperatorWatchItems,
  formatLeaguesByState,
  type AdminOverview,
  type OperatorWatchTarget,
} from "@fantappero/contracts";
import { Breadcrumb, PageContainer, UiStatePanel } from "@fantappero/ui";
import { useCallback, useEffect, useState } from "react";
import { fetchAdminOverview } from "../api/admin";
import { ApiError } from "../api/client";
import { getApiErrorMessage } from "../auth/AuthContext";
import { loadStoredSession } from "../auth/sessionStorage";
import { ADMIN_NAV_ITEMS } from "../navigation/navConfig";
import { Link } from "../router/simpleRouter";

/** Pagina della voce di menù a cui porta una riga di «Da guardare». */
function targetPath(target: OperatorWatchTarget): string {
  return ADMIN_NAV_ITEMS.find((item) => item.id === target)?.path ?? "/admin";
}

/**
 * «Riepilogo» del pannello operatore (release 1.4, canvas «Pannello operatore» approvato da
 * Rosario il 22/11): chi sei e l'ambiente, i numeri, le leghe per stato e «Da guardare», le cose
 * che aspettano l'operatore, ognuna con il link alla sua sezione. Niente schede che ripetono il
 * menù; la versione dell'app ha la sua voce «Versione app».
 */
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

  const leagueStates = overview ? formatLeaguesByState(overview.leaguesByState) : "";
  const watchItems = overview?.watch ? buildOperatorWatchItems(overview.watch, new Date()) : null;

  return (
    <PageContainer title="Riepilogo" header={<Breadcrumb items={[{ label: "Operazioni" }]} />}>
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
        <div className="fa-admin-summary" data-testid="admin-dashboard-success">
          <p className="fa-admin-summary__id">
            <strong data-testid="admin-overview-name">{overview.operatorDisplayName}</strong>
            <span>operatore</span>
            <span className="fa-admin-summary__env" data-testid="admin-overview-environment">
              {overview.environment}
            </span>
          </p>
          <section aria-labelledby="admin-overview-counts">
            <h2 id="admin-overview-counts" className="fa-sr-only">
              Numeri della piattaforma
            </h2>
            <ul className="fa-admin-summary__kpis">
              <li>
                <strong data-testid="admin-overview-users">{overview.usersCount}</strong>
                <span>Utenti</span>
              </li>
              <li>
                <strong data-testid="admin-overview-operators">{overview.operatorsCount}</strong>
                <span>Operatori</span>
              </li>
              <li>
                <strong data-testid="admin-overview-leagues">{overview.leaguesCount}</strong>
                <span>Leghe</span>
              </li>
            </ul>
            {leagueStates ? (
              <p className="fa-admin-summary__states" data-testid="admin-overview-league-states">
                Leghe: {leagueStates}
              </p>
            ) : null}
          </section>
          <section aria-labelledby="admin-watch-title">
            <h2 id="admin-watch-title" className="fa-admin-summary__label">
              Da guardare
            </h2>
            {watchItems ? (
              <ul className="fa-admin-watch" data-testid="admin-watch">
                {watchItems.map((row) => (
                  <li key={row.id} data-testid={`admin-watch-${row.id}`} data-tone={row.tone}>
                    <Link to={targetPath(row.target)} className="fa-admin-watch__row">
                      <span
                        className={`fa-admin-watch__dot fa-admin-watch__dot--${row.tone}`}
                        aria-hidden="true"
                      />
                      <span className="fa-admin-watch__text">
                        <strong>{row.title}</strong>
                        {row.details.map((detail) => (
                          <span key={detail}>{detail}</span>
                        ))}
                      </span>
                      <span className="fa-admin-watch__go">
                        {row.targetLabel}
                        <span aria-hidden="true"> ›</span>
                      </span>
                    </Link>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="fa-admin-summary__note" data-testid="admin-watch-unavailable">
                Le cose da guardare non sono disponibili in questo momento. Le sezioni restano nel
                menù.
              </p>
            )}
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
