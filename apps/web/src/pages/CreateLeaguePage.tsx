import type { CompetitionSummary, LeagueDetail } from "@fantappero/contracts";
import {
  Breadcrumb,
  Button,
  Input,
  PageContainer,
  Select,
  UiStatePanel,
} from "@fantappero/ui";
import { type FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { createLeague, fetchCompetitions } from "../api/leagues";
import { getApiErrorMessage, useAuth } from "../auth/AuthContext";
import { ManagerDirectory } from "../components/ManagerDirectory";
import { loadStoredSession } from "../auth/sessionStorage";
import { Link, useLocation, useNavigate } from "../router/simpleRouter";
import { parseWireframeStateFromSearch } from "../wireframes/useWireframeState";

const DEMO_COMPETITIONS: CompetitionSummary[] = [
  { id: "demo-39", providerId: 39, name: "Premier League", country: "England" },
  { id: "demo-140", providerId: 140, name: "La Liga", country: "Spain" },
  { id: "demo-135", providerId: 135, name: "Serie A", country: "Italy" },
  { id: "demo-78", providerId: 78, name: "Bundesliga", country: "Germany" },
  { id: "demo-61", providerId: 61, name: "Ligue 1", country: "France" },
];

function buildSeasonOptions(): Array<{ value: string; label: string }> {
  const currentYear = new Date().getFullYear();
  return [currentYear - 1, currentYear, currentYear + 1].map((year) => ({
    value: String(year),
    label: String(year),
  }));
}

/** Configurazione iniziale di una lega privata in bozza (EP03-01). */
export function CreateLeaguePage() {
  const navigate = useNavigate();
  const { isDemoMode, registerLeague } = useAuth();
  const { search } = useLocation();
  const demoState = isDemoMode ? parseWireframeStateFromSearch(search) : null;
  const seasonOptions = useMemo(() => buildSeasonOptions(), []);
  const defaultSeason = String(new Date().getFullYear());

  const [competitions, setCompetitions] = useState<CompetitionSummary[]>(() =>
    isDemoMode && demoState !== "empty" ? DEMO_COMPETITIONS : [],
  );
  const [loadingCatalog, setLoadingCatalog] = useState(() =>
    isDemoMode ? demoState === "loading" : true,
  );
  const [catalogError, setCatalogError] = useState<string | null>(() =>
    isDemoMode && demoState === "error" ? "Impossibile caricare i campionati (demo)." : null,
  );

  const [name, setName] = useState("");
  const [seasonYear, setSeasonYear] = useState(defaultSeason);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [formError, setFormError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [createdLeague, setCreatedLeague] = useState<LeagueDetail | null>(null);

  const loadCatalog = useCallback(async () => {
    if (isDemoMode) {
      if (demoState === "loading") {
        setLoadingCatalog(true);
        setCatalogError(null);
        setCompetitions([]);
        return;
      }
      if (demoState === "error") {
        setLoadingCatalog(false);
        setCatalogError("Impossibile caricare i campionati (demo).");
        setCompetitions([]);
        return;
      }
      if (demoState === "empty") {
        setLoadingCatalog(false);
        setCatalogError(null);
        setCompetitions([]);
        return;
      }
      setCompetitions(DEMO_COMPETITIONS);
      setLoadingCatalog(false);
      return;
    }

    const stored = loadStoredSession();
    if (!stored?.accessToken) {
      setCatalogError("Sessione non disponibile. Accedi di nuovo.");
      setLoadingCatalog(false);
      return;
    }

    setLoadingCatalog(true);
    setCatalogError(null);
    try {
      const rows = await fetchCompetitions(stored.accessToken);
      setCompetitions(rows);
    } catch (error) {
      setCatalogError(getApiErrorMessage(error, "Impossibile caricare i campionati."));
    } finally {
      setLoadingCatalog(false);
    }
  }, [demoState, isDemoMode]);

  useEffect(() => {
    void loadCatalog();
  }, [loadCatalog]);

  function toggleCompetition(competitionId: string) {
    setSelectedIds((current) => {
      const next = new Set(current);
      if (next.has(competitionId)) {
        next.delete(competitionId);
      } else {
        next.add(competitionId);
      }
      return next;
    });
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setFormError(null);

    if (!name.trim()) {
      setFormError("Inserisci un nome per la lega.");
      return;
    }
    if (selectedIds.size < 3) {
      setFormError("Seleziona almeno 3 campionati.");
      return;
    }

    if (isDemoMode) {
      setCreatedLeague({
        id: "demo-created-league",
        name: name.trim(),
        seasonYear: Number(seasonYear),
        state: "draft",
        viewerRole: "league_admin",
        competitions: DEMO_COMPETITIONS.filter((row) => selectedIds.has(row.id)),
        rules: {
          presetName: "standard",
          participantCount: 8,
          participantMin: 4,
          participantMax: 10,
          roster: {
            rosterSize: 35,
            goalkeepers: 3,
            defenders: 11,
            midfielders: 11,
            forwards: 10,
          },
          totalCredits: 1000,
          options: {
            allowTrades: true,
            allowManualInvites: true,
          },
        },
      });
      return;
    }

    const stored = loadStoredSession();
    if (!stored?.accessToken) {
      setFormError("Sessione non disponibile. Accedi di nuovo.");
      return;
    }

    setSubmitting(true);
    try {
      const created = await createLeague(stored.accessToken, {
        name: name.trim(),
        seasonYear: Number(seasonYear),
        competitionIds: [...selectedIds],
      });
      registerLeague({
        id: created.id,
        name: created.name,
        role: created.viewerRole === "league_admin" ? "league_admin" : "member",
      });
      setCreatedLeague(created);
    } catch (error) {
      setFormError(getApiErrorMessage(error, "Impossibile creare la lega."));
    } finally {
      setSubmitting(false);
    }
  }

  if (createdLeague) {
    return (
      <PageContainer
        title="Lega creata"
        header={
          <Breadcrumb
            items={[
              { label: "Leghe", href: "/leghe" },
              { label: "Crea lega" },
            ]}
          />
        }
      >
        <UiStatePanel
          state="success"
          title="Fase 1 completata: lega salvata"
          message={`"${createdLeague.name}" è pronta per la configurazione. Sei amministratore della lega.`}
          testId="create-league-success"
        />
        <ManagerDirectory
          leagueId={createdLeague.id}
          isDemoMode={isDemoMode}
          search={search}
          title="Fase 2 (facoltativa): invita fantallenatori"
          compact
        />
        <div className="fa-ds-showcase__row" style={{ marginTop: "1rem" }}>
          <Button variant="primary" onClick={() => navigate("/leghe")} data-testid="create-league-done">
            Concludi
          </Button>
          <Link to="/lega/amministrazione">
            <Button variant="secondary">Amministrazione lega</Button>
          </Link>
        </div>
      </PageContainer>
    );
  }

  return (
    <PageContainer
      title="Crea lega"
      header={
        <Breadcrumb
          items={[
            { label: "Leghe", href: "/leghe" },
            { label: "Crea lega" },
          ]}
        />
      }
    >
      {loadingCatalog ? (
        <UiStatePanel
          state="loading"
          title="Caricamento campionati"
          message="Recupero del catalogo MVP in corso…"
          testId="create-league-loading"
        />
      ) : null}

      {!loadingCatalog && catalogError ? (
        <UiStatePanel
          state="error"
          title="Errore di caricamento"
          message={catalogError}
          testId="create-league-catalog-error"
        />
      ) : null}

      {!loadingCatalog && !catalogError && competitions.length === 0 ? (
        <UiStatePanel
          state="empty"
          title="Nessun campionato disponibile"
          message="Il catalogo campionati non è al momento disponibile."
          testId="create-league-empty"
        />
      ) : null}

      {!loadingCatalog && !catalogError && competitions.length > 0 ? (
        <form data-testid="create-league-form" onSubmit={(event) => void handleSubmit(event)}>
          <Input
            label="Nome lega"
            name="league-name"
            value={name}
            onChange={(event) => setName(event.target.value)}
            required
          />
          <Select
            label="Stagione"
            name="season-year"
            value={seasonYear}
            onChange={(event) => setSeasonYear(event.target.value)}
            options={seasonOptions}
          />

          <fieldset data-testid="create-league-competitions">
            <legend>Campionati (minimo 3)</legend>
            <ul className="fa-wireframe-list">
              {competitions.map((competition) => (
                <li key={competition.id}>
                  <label>
                    <input
                      type="checkbox"
                      name="competition"
                      value={competition.id}
                      checked={selectedIds.has(competition.id)}
                      onChange={() => toggleCompetition(competition.id)}
                    />{" "}
                    {competition.name} ({competition.country})
                  </label>
                </li>
              ))}
            </ul>
          </fieldset>

          {formError ? (
            <UiStatePanel
              state="error"
              title="Impossibile creare la lega"
              message={formError}
              testId="create-league-error"
            />
          ) : null}

          <div className="fa-ds-showcase__row">
            <Button
              type="submit"
              variant="primary"
              disabled={submitting}
              data-testid="create-league-submit"
            >
              {submitting ? "Creazione in corso…" : "Crea lega privata"}
            </Button>
            <Link to="/leghe">
              <Button type="button" variant="ghost">
                Annulla
              </Button>
            </Link>
          </div>
        </form>
      ) : null}

      {!loadingCatalog && catalogError ? (
        <Button variant="ghost" onClick={() => void loadCatalog()} data-testid="create-league-retry">
          Ricarica campionati
        </Button>
      ) : null}
    </PageContainer>
  );
}
