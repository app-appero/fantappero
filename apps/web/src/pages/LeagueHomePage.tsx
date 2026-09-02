import type {
  LeagueCalendar,
  LeagueDetail,
  LeagueMember,
} from "@fantappero/contracts";
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
import {
  fetchLeague,
  fetchLeagueCalendar,
  fetchLeagueMembersPublic,
} from "../api/leagues";
import { getApiErrorMessage, useAuth } from "../auth/AuthContext";
import { leagueStateLabel } from "../leagues/leagueLabels";
import { loadStoredSession } from "../auth/sessionStorage";
import { Link, useLocation } from "../router/simpleRouter";
import { parseWireframeStateFromSearch } from "../wireframes/useWireframeState";

const DEMO_LEAGUE: LeagueDetail = {
  id: "lega-demo",
  name: "Lega Demo",
  seasonYear: 2026,
  state: "configuring",
  viewerRole: "member",
  competitions: [
    { id: "c1", providerId: 39, name: "Premier League", country: "England" },
    { id: "c2", providerId: 140, name: "La Liga", country: "Spain" },
    { id: "c3", providerId: 135, name: "Serie A", country: "Italy" },
  ],
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
    minFixturesPerRound: 25,
    turnCoverageThreshold: 0.75,
    lineupLockMarginMinutes: 15,
    minutesThreshold: 15,
    voluntaryReleaseRefundPercent: 50,
    leagueExitRefundPercent: 100,
    maxActiveTradeProposalsPerTeam: 10,
    options: { allowTrades: true, allowManualInvites: true, requireTradeApproval: false },
  },
};

const DEMO_MEMBERS: LeagueMember[] = [
  {
    userId: "user-1",
    displayName: "Marco Rossi",
    userType: "human",
    role: "league_admin",
    joinedAt: "2026-07-01T10:00:00Z",
  },
  {
    userId: "user-2",
    displayName: "Giulia Bianchi",
    userType: "human",
    role: "member",
    joinedAt: "2026-07-02T10:00:00Z",
  },
];

const DEMO_CALENDAR: LeagueCalendar = {
  id: "cal-1",
  leagueId: "lega-demo",
  status: "confirmed",
  format: "single_round_robin",
  algorithmVersion: "v1",
  participantCount: 8,
  roundCount: 7,
  matchupCount: 28,
  byeCount: 0,
  generatedAt: "2026-08-01T10:00:00Z",
  confirmedAt: "2026-08-01T12:00:00Z",
  rounds: [],
  summary: { message: "Calendario confermato (demo)." },
};

/** Home lega minima M1: contesto, regolamento, partecipanti, placeholder M2 (EP03-UX-02). */
export function LeagueHomePage() {
  const { isDemoMode, activeLeagueId, activeLeague, can } = useAuth();
  const { search } = useLocation();
  const demoState = isDemoMode ? parseWireframeStateFromSearch(search) : null;
  const params = new URLSearchParams(search);
  const calendarDemo = params.get("calendario");

  const [league, setLeague] = useState<LeagueDetail | null>(() =>
    isDemoMode && demoState !== "empty" && demoState !== "error" ? DEMO_LEAGUE : null,
  );
  const [members, setMembers] = useState<LeagueMember[]>(() =>
    isDemoMode && demoState !== "empty" && demoState !== "error" ? DEMO_MEMBERS : [],
  );
  const [calendar, setCalendar] = useState<LeagueCalendar | null>(() =>
    isDemoMode && calendarDemo !== "empty" && demoState !== "empty" && demoState !== "error"
      ? DEMO_CALENDAR
      : null,
  );
  const [loading, setLoading] = useState(() =>
    isDemoMode ? demoState === "loading" : true,
  );
  const [loadError, setLoadError] = useState<string | null>(() =>
    isDemoMode && demoState === "error" ? "Impossibile caricare la home lega (demo)." : null,
  );

  const loadHome = useCallback(async () => {
    if (isDemoMode) {
      if (demoState === "loading") {
        setLoading(true);
        setLeague(null);
        setMembers([]);
        setCalendar(null);
        setLoadError(null);
        return;
      }
      if (demoState === "error") {
        setLoading(false);
        setLeague(null);
        setMembers([]);
        setCalendar(null);
        setLoadError("Impossibile caricare la home lega (demo).");
        return;
      }
      if (demoState === "empty") {
        setLoading(false);
        setLeague(null);
        setMembers([]);
        setCalendar(null);
        setLoadError(null);
        return;
      }
      setLeague({
        ...DEMO_LEAGUE,
        id: activeLeagueId ?? DEMO_LEAGUE.id,
        name: activeLeague?.name ?? DEMO_LEAGUE.name,
        viewerRole: activeLeague?.role ?? "member",
      });
      setMembers(DEMO_MEMBERS);
      setCalendar(calendarDemo === "empty" ? null : DEMO_CALENDAR);
      setLoading(false);
      setLoadError(null);
      return;
    }

    if (!activeLeagueId) {
      setLoading(false);
      setLeague(null);
      setMembers([]);
      setCalendar(null);
      setLoadError(null);
      return;
    }

    const stored = loadStoredSession();
    if (!stored?.accessToken) {
      setLoading(false);
      setLoadError("Sessione non disponibile. Accedi di nuovo.");
      return;
    }

    setLoading(true);
    setLoadError(null);
    try {
      const [detail, roster, cal] = await Promise.all([
        fetchLeague(stored.accessToken, activeLeagueId),
        fetchLeagueMembersPublic(stored.accessToken, activeLeagueId),
        fetchLeagueCalendar(stored.accessToken, activeLeagueId),
      ]);
      setLeague(detail);
      setMembers(roster);
      setCalendar(cal);
    } catch (error) {
      setLoadError(getApiErrorMessage(error, "Impossibile caricare la home della lega."));
      setLeague(null);
      setMembers([]);
      setCalendar(null);
    } finally {
      setLoading(false);
    }
  }, [activeLeague, activeLeagueId, calendarDemo, demoState, isDemoMode]);

  useEffect(() => {
    void loadHome();
  }, [loadHome]);

  const isAdmin = league?.viewerRole === "league_admin" || can(["league:admin"]);

  return (
    <PageContainer
      title={league?.name ?? "Home lega"}
      header={
        <Breadcrumb
          items={[
            { label: "Leghe", href: "/leghe" },
            { label: league?.name ?? "Home" },
          ]}
        />
      }
    >
      {loading ? (
        <UiStatePanel
          state="loading"
          title="Caricamento home lega"
          message="Recupero contesto, regolamento e partecipanti…"
          testId="league-home-loading"
        />
      ) : null}

      {!loading && loadError ? (
        <div>
          <UiStatePanel
            state="error"
            title="Home non disponibile"
            message={loadError}
            testId="league-home-error"
          />
          <Button type="button" variant="ghost" onClick={() => void loadHome()}>
            Riprova
          </Button>
        </div>
      ) : null}

      {!loading && !loadError && !league ? (
        <UiStatePanel
          state="empty"
          title="Nessuna lega selezionata"
          message="Scegli una lega dal selettore in alto, creane una o unisciti con un codice invito."
          testId="league-home-empty"
        />
      ) : null}

      {!loading && !loadError && league ? (
        <div data-testid="league-home-content">
          <section aria-labelledby="league-home-context-title">
            <h2 id="league-home-context-title">Contesto</h2>
            <p>
              Stato: <strong>{leagueStateLabel(league.state)}</strong>
            </p>
            <p>
              Ruolo:{" "}
              <strong>
                {league.viewerRole === "league_admin" ? "Amministratore" : "Partecipante"}
              </strong>
            </p>
            <p>Stagione: {league.seasonYear}</p>
            {isAdmin ? (
              <Link to={`/lega/amministrazione?leagueId=${league.id}`}>
                <Button variant="secondary" data-testid="league-home-admin-link">
                  Amministrazione lega
                </Button>
              </Link>
            ) : null}
          </section>

          <section aria-labelledby="league-home-rules-title" style={{ marginTop: "1.5rem" }}>
            <h2 id="league-home-rules-title">Regolamento</h2>
            {league.rules ? (
              <Card>
                <CardHeader>Preset {league.rules.presetName}</CardHeader>
                <CardBody>
                  <p>Partecipanti previsti: {league.rules.participantCount}</p>
                  <p>Crediti iniziali: {league.rules.totalCredits}</p>
                  <p>
                    Rosa: {league.rules.roster.rosterSize} giocatori (
                    {league.rules.roster.goalkeepers}P-{league.rules.roster.defenders}D-
                    {league.rules.roster.midfielders}C-{league.rules.roster.forwards}A)
                  </p>
                  <p>
                    Campionati:{" "}
                    {league.competitions.map((competition) => competition.name).join(", ") || "—"}
                  </p>
                </CardBody>
              </Card>
            ) : (
              <UiStatePanel
                state="empty"
                title="Regolamento non impostato"
                message="L'amministratore deve ancora completare la configurazione."
                testId="league-home-rules-empty"
              />
            )}
          </section>

          <section aria-labelledby="league-home-members-title" style={{ marginTop: "1.5rem" }}>
            <h2 id="league-home-members-title">Partecipanti</h2>
            {members.length === 0 ? (
              <UiStatePanel
                state="empty"
                title="Nessun partecipante"
                message="Non risultano iscritti in questa lega."
                testId="league-home-members-empty"
              />
            ) : (
              <ul className="fa-league-list" data-testid="league-home-members-list">
                {members.map((member) => (
                  <li key={member.userId} className="fa-league-list__item">
                    <span>
                      <strong>{member.displayName}</strong>
                      {` · ${member.role === "league_admin" ? "Amministratore" : "Partecipante"}`}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </section>

          <section aria-labelledby="league-home-calendar-title" style={{ marginTop: "1.5rem" }}>
            <h2 id="league-home-calendar-title">Calendario</h2>
            {calendar ? (
              <UiStatePanel
                state="success"
                title="Calendario confermato"
                message={`${calendar.roundCount} giornate · ${calendar.matchupCount} scontri · formato a girone unico.`}
                testId="league-home-calendar"
              />
            ) : (
              <UiStatePanel
                state="empty"
                title="Calendario non disponibile"
                message="Il calendario scontri diretti non è ancora stato generato o confermato."
                testId="league-home-calendar-empty"
              />
            )}
          </section>

          <section aria-labelledby="league-home-next-title" style={{ marginTop: "1.5rem" }}>
            <h2 id="league-home-next-title">Prossime fasi</h2>
            <p>Funzioni di gioco disponibili dalla prossima fase.</p>
            <div className="fa-ds-showcase__row">
              <Link to="/rosa" data-testid="league-home-roster-link">
                Vai alla rosa
              </Link>
              <Link to="/formazione" data-testid="league-home-formation-link">
                Vai alla formazione
              </Link>
              <Link to="/turni" data-testid="league-home-matchday-link">
                Vai ai turni
              </Link>
            </div>
          </section>
        </div>
      ) : null}
    </PageContainer>
  );
}
