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
import { fetchMyLeagues } from "../api/leagues";
import { getApiErrorMessage, useAuth } from "../auth/AuthContext";
import { loadStoredSession } from "../auth/sessionStorage";
import { Link, useLocation } from "../router/simpleRouter";
import { parseWireframeStateFromSearch } from "../wireframes/useWireframeState";

const DEMO_LEAGUES: LeagueSummary[] = [
  { id: "demo-league-1", name: "Lega Demo", role: "league_admin", state: "configuring" },
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

/** Elenco leghe dell'utente con stato vuoto e azione di creazione (EP03-01). */
export function LeaguesPage() {
  const { isDemoMode } = useAuth();
  const { search } = useLocation();
  const demoState = isDemoMode ? parseWireframeStateFromSearch(search) : null;
  const [leagues, setLeagues] = useState<LeagueSummary[]>(() =>
    isDemoMode && demoState !== "empty" ? DEMO_LEAGUES : [],
  );
  const [loading, setLoading] = useState(() =>
    isDemoMode ? demoState === "loading" : true,
  );
  const [loadError, setLoadError] = useState<string | null>(() =>
    isDemoMode && demoState === "error" ? "Impossibile caricare le leghe (demo)." : null,
  );

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
      setLeagues(DEMO_LEAGUES);
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
  }, [demoState, isDemoMode]);

  useEffect(() => {
    void loadLeagues();
  }, [loadLeagues]);

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
          message="Non partecipi ancora a nessuna lega privata. Creane una per iniziare la configurazione."
          testId="leagues-empty"
        />
      ) : null}

      {!loading && !loadError && leagues.length > 0 ? (
        <section data-testid="leagues-list">
          <ul className="fa-league-list">
            {leagues.map((league) => (
              <li key={league.id} className="fa-league-list__item">
                <Card>
                  <CardHeader>{league.name}</CardHeader>
                  <CardBody>
                    <p>
                      Ruolo:{" "}
                      {league.role === "league_admin" ? "Amministratore" : "Partecipante"}
                    </p>
                    <p>Stato: {leagueStateLabel(league.state)}</p>
                    {league.role === "league_admin" ? (
                      <Link to={`/lega/amministrazione?leagueId=${league.id}`}>
                        <Button
                          variant="ghost"
                          data-testid={`league-admin-link-${league.id}`}
                          style={{ marginTop: "0.5rem" }}
                        >
                          Amministrazione lega
                        </Button>
                      </Link>
                    ) : null}
                  </CardBody>
                </Card>
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      <div className="fa-ds-showcase__row" style={{ marginTop: "1rem" }}>
        <Link to="/leghe/crea">
          <Button variant="secondary" data-testid="leagues-create-link">
            Crea lega
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
