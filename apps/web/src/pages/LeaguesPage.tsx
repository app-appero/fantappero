import type { LeagueState, LeagueSummary } from "@fantappero/contracts";
import {
  Breadcrumb,
  Button,
  Card,
  CardBody,
  CardHeader,
  PageContainer,
  UiStatePanel,
} from "@fantappero/ui";
import { useCallback, useEffect, useState } from "react";
import { deleteLeague, fetchMyLeagues } from "../api/leagues";
import { getApiErrorMessage, useAuth } from "../auth/AuthContext";
import { loadStoredSession } from "../auth/sessionStorage";
import { Link, useLocation, useNavigate } from "../router/simpleRouter";
import { parseWireframeStateFromSearch } from "../wireframes/useWireframeState";
import { isLeagueDeletable } from "./leagueDeleteHelpers";

const DEMO_LEAGUES: LeagueSummary[] = [
  { id: "demo-league-1", name: "Lega Demo", role: "league_admin", state: "configuring" },
  { id: "demo-league-2", name: "Lega Amici", role: "member", state: "draft" },
  { id: "demo-league-3", name: "Lega Bozza Admin", role: "league_admin", state: "draft" },
];

function leagueStateLabel(state: LeagueState | undefined): string {
  return state
    ? {
        draft: "Bozza",
        configuring: "Configurazione",
        auction: "Asta",
        active: "Attiva",
        concluded: "Conclusa",
        archived: "Archiviata",
      }[state]
    : "—";
}

/** Elenco leghe dell'utente con ingresso contesto e azioni rapide (EP03-UX-01). */
export function LeaguesPage() {
  const { isDemoMode, setActiveLeagueId, unregisterLeague } = useAuth();
  const { search } = useLocation();
  const navigate = useNavigate();
  const demoState = isDemoMode ? parseWireframeStateFromSearch(search) : null;
  const persona = new URLSearchParams(search).get("persona");
  const [leagues, setLeagues] = useState<LeagueSummary[]>(() => {
    if (!isDemoMode || demoState === "empty") {
      return [];
    }
    if (persona === "member") {
      return DEMO_LEAGUES.map((league) => ({ ...league, role: "member" as const }));
    }
    return DEMO_LEAGUES;
  });
  const [loading, setLoading] = useState(() =>
    isDemoMode ? demoState === "loading" : true,
  );
  const [loadError, setLoadError] = useState<string | null>(() =>
    isDemoMode && demoState === "error" ? "Impossibile caricare le leghe (demo)." : null,
  );
  const [pendingDeleteId, setPendingDeleteId] = useState<string | null>(null);
  const [deleteConfirmed, setDeleteConfirmed] = useState(false);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  const loadLeagues = useCallback(async () => {
    if (isDemoMode) {
      if (demoState === "loading") {
        setLoading(true);
        setLoadError(null);
        setLeagues([]);
        return;
      }
      if (demoState === "error") {
        setLoading(false);
        setLoadError("Impossibile caricare le leghe (demo).");
        setLeagues([]);
        return;
      }
      if (demoState === "empty") {
        setLoading(false);
        setLoadError(null);
        setLeagues([]);
        return;
      }
      setLeagues(
        persona === "member"
          ? DEMO_LEAGUES.map((league) => ({ ...league, role: "member" as const }))
          : DEMO_LEAGUES,
      );
      setLoading(false);
      return;
    }

    const stored = loadStoredSession();
    if (!stored?.accessToken) {
      setLoadError("Sessione non disponibile. Accedi di nuovo.");
      setLoading(false);
      return;
    }

    setLoading(true);
    setLoadError(null);
    try {
      const rows = await fetchMyLeagues(stored.accessToken);
      setLeagues(rows);
    } catch (error) {
      setLoadError(getApiErrorMessage(error, "Impossibile caricare le leghe."));
    } finally {
      setLoading(false);
    }
  }, [demoState, isDemoMode, persona]);

  useEffect(() => {
    void loadLeagues();
  }, [loadLeagues]);

  function enterLeague(league: LeagueSummary) {
    setActiveLeagueId(league.id);
    navigate(`/lega/home?leagueId=${league.id}`);
  }

  function beginDelete(leagueId: string) {
    setDeleteError(null);
    setDeleteConfirmed(false);
    setPendingDeleteId(leagueId);
  }

  function cancelDelete() {
    setPendingDeleteId(null);
    setDeleteConfirmed(false);
    setDeleteError(null);
  }

  async function confirmDelete(league: LeagueSummary) {
    setDeleteError(null);
    if (!deleteConfirmed) {
      setDeleteError("Conferma esplicitamente l'eliminazione spuntando la casella.");
      return;
    }
    if (isDemoMode) {
      setLeagues((current) => current.filter((row) => row.id !== league.id));
      cancelDelete();
      return;
    }
    const stored = loadStoredSession();
    if (!stored?.accessToken) {
      setDeleteError("Sessione non disponibile. Accedi di nuovo.");
      return;
    }
    setDeletingId(league.id);
    try {
      await deleteLeague(stored.accessToken, league.id);
      unregisterLeague(league.id);
      setLeagues((current) => current.filter((row) => row.id !== league.id));
      cancelDelete();
    } catch (error) {
      setDeleteError(getApiErrorMessage(error, "Impossibile eliminare la lega."));
    } finally {
      setDeletingId(null);
    }
  }

  return (
    <PageContainer
      title="Le tue leghe"
      header={<Breadcrumb items={[{ label: "Leghe" }]} />}
    >
      {loading ? (
        <UiStatePanel
          state="loading"
          title="Caricamento leghe"
          message="Recupero delle leghe in corso…"
          testId="leagues-loading"
        />
      ) : null}

      {!loading && loadError ? (
        <UiStatePanel
          state="error"
          title="Errore di caricamento"
          message={loadError}
          testId="leagues-error"
        />
      ) : null}

      {!loading && !loadError && leagues.length === 0 ? (
        <UiStatePanel
          state="empty"
          title="Nessuna lega"
          message="Non partecipi ancora a nessuna lega privata. Creane una oppure unisciti con un codice invito."
          testId="leagues-empty"
        />
      ) : null}

      {!loading && !loadError && leagues.length > 0 ? (
        <section data-testid="leagues-list">
          <ul className="fa-league-list">
            {leagues.map((league) => {
              const canDelete =
                league.role === "league_admin" && isLeagueDeletable(league.state);
              const isPending = pendingDeleteId === league.id;

              return (
                <li key={league.id} className="fa-league-list__item">
                  <Card>
                    <CardHeader>{league.name}</CardHeader>
                    <CardBody>
                      <p>
                        Ruolo:{" "}
                        {league.role === "league_admin" ? "Amministratore" : "Partecipante"}
                      </p>
                      <p>Stato: {leagueStateLabel(league.state)}</p>
                      <div className="fa-ds-showcase__row" style={{ marginTop: "0.5rem" }}>
                        <Button
                          variant="primary"
                          data-testid={`league-enter-${league.id}`}
                          onClick={() => enterLeague(league)}
                        >
                          Entra in lega
                        </Button>
                        {league.role === "league_admin" ? (
                          <Link to={`/lega/amministrazione?leagueId=${league.id}`}>
                            <Button
                              variant="ghost"
                              data-testid={`league-admin-link-${league.id}`}
                            >
                              Amministrazione lega
                            </Button>
                          </Link>
                        ) : null}
                        {canDelete && !isPending ? (
                          <Button
                            type="button"
                            variant="danger"
                            data-testid={`league-delete-${league.id}`}
                            onClick={() => beginDelete(league.id)}
                          >
                            Elimina lega
                          </Button>
                        ) : null}
                      </div>
                      {canDelete && isPending ? (
                        <div
                          className="fa-league-delete fa-league-delete--inline"
                          data-testid={`league-delete-confirm-panel-${league.id}`}
                        >
                          <p>
                            L&apos;eliminazione è definitiva. Disponibile solo in bozza o
                            configurazione.
                          </p>
                          <label>
                            <input
                              type="checkbox"
                              checked={deleteConfirmed}
                              data-testid={`league-delete-confirm-${league.id}`}
                              onChange={(event) => setDeleteConfirmed(event.target.checked)}
                            />{" "}
                            Confermo di voler eliminare definitivamente «{league.name}»
                          </label>
                          {deleteError ? (
                            <UiStatePanel
                              state="error"
                              title="Eliminazione non riuscita"
                              message={deleteError}
                              testId="leagues-delete-error"
                            />
                          ) : null}
                          <div className="fa-ds-showcase__row" style={{ marginTop: "0.5rem" }}>
                            <Button
                              type="button"
                              variant="danger"
                              loading={deletingId === league.id}
                              disabled={!deleteConfirmed}
                              data-testid={`league-delete-submit-${league.id}`}
                              onClick={() => void confirmDelete(league)}
                            >
                              Conferma eliminazione
                            </Button>
                            <Button
                              type="button"
                              variant="ghost"
                              data-testid={`league-delete-cancel-${league.id}`}
                              onClick={cancelDelete}
                            >
                              Annulla
                            </Button>
                          </div>
                        </div>
                      ) : null}
                    </CardBody>
                  </Card>
                </li>
              );
            })}
          </ul>
        </section>
      ) : null}

      <div className="fa-ds-showcase__row" style={{ marginTop: "1rem" }}>
        <Link to="/leghe/crea">
          <Button variant="secondary" data-testid="leagues-create-link">
            Crea lega
          </Button>
        </Link>
        <Link to="/leghe/invito">
          <Button variant="ghost" data-testid="leagues-join-link">
            Unisciti con codice
          </Button>
        </Link>
        {!loading && loadError ? (
          <Button variant="ghost" onClick={() => void loadLeagues()} data-testid="leagues-retry">
            Ricarica
          </Button>
        ) : null}
      </div>
    </PageContainer>
  );
}
