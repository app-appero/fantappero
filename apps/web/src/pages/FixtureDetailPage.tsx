import type {
  FixtureLineup,
  FixtureLineupPlayer,
  FixtureLiveDetail,
  FixtureTimelineEvent,
  MatchBadge,
  ProviderFeedState,
} from "@fantappero/contracts";
import { layoutFromGrid, mapFixtureMatchStatus, realMatchBadgesByAthlete } from "@fantappero/contracts";
import type { TimelineEntry } from "@fantappero/ui";
import {
  AssistIcon,
  Badge,
  Breadcrumb,
  Button,
  FootballPitch,
  GoalIcon,
  MatchTimeline,
  OwnGoalIcon,
  PageContainer,
  PenaltyIcon,
  PenaltyMissedIcon,
  RedCardIcon,
  RoleBadge,
  SubstitutionInIcon,
  SubstitutionOutIcon,
  UiStatePanel,
  VarIcon,
  YellowCardIcon,
} from "@fantappero/ui";
import { type ReactNode, useCallback, useEffect, useState } from "react";
import { fetchFixtureLiveDetail } from "../api/leagues";
import { getApiErrorMessage, useAuth } from "../auth/AuthContext";
import { loadStoredSession } from "../auth/sessionStorage";
import { useLiveFixturePolling } from "../matchday/useLiveFixturePolling";
import { Link, useLocation } from "../router/simpleRouter";

const KICKOFF_FORMAT = new Intl.DateTimeFormat("it-IT", {
  dateStyle: "short",
  timeStyle: "short",
});

/** Stato partita in copy italiano, senza inventare ciò che il provider non dice. */
const STATUS_LABELS: Record<string, string> = {
  NS: "Non iniziata",
  "1H": "Primo tempo",
  HT: "Intervallo",
  "2H": "Secondo tempo",
  ET: "Supplementari",
  BT: "Pausa supplementari",
  P: "Rigori",
  LIVE: "In corso",
  INT: "Interrotta",
  SUSP: "Sospesa",
  FT: "Finita",
  AET: "Finita dopo i supplementari",
  PEN: "Finita ai rigori",
  PST: "Rinviata",
  CANC: "Annullata",
  ABD: "Abbandonata",
  AWD: "Vittoria a tavolino",
  WO: "Walkover",
};

const FEED_VARIANTS: Record<ProviderFeedState, "success" | "warning" | "neutral"> = {
  fresh: "success",
  delayed: "warning",
  stale: "warning",
  degraded: "warning",
  unavailable: "neutral",
};

export function statusLabel(statusShort: string, statusElapsed: number | null): string {
  const base = STATUS_LABELS[statusShort.toUpperCase()] ?? statusShort;
  return statusElapsed === null ? base : `${base} · ${statusElapsed}'`;
}

function formatKickoff(value: string | null): string {
  if (!value) {
    return "Orario non disponibile";
  }
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? "Orario non disponibile" : KICKOFF_FORMAT.format(parsed);
}

/** Id stabile per collegare un giocatore alla sua posizione sul campo; l'id dell'atleta resta la chiave per i badge evento. */
function pitchPlayerId(player: FixtureLineupPlayer): string {
  return player.athleteId ?? `${player.name}-${player.shirtNumber ?? ""}`;
}

function toPitchPlayers(players: readonly FixtureLineupPlayer[], badgesByAthlete: Map<string, MatchBadge[]>) {
  return players.map((player) => ({
    id: pitchPlayerId(player),
    shirtNumber: player.shirtNumber,
    name: player.name,
    role: player.position,
    badges: player.athleteId ? badgesByAthlete.get(player.athleteId) : undefined,
    photoUrl: player.photoUrl,
  }));
}

/** Stato reale del panchinaro (§14): non un fisso "può subentrare" a partita finita. */
function benchStatusLabel(player: FixtureLineupPlayer, events: readonly FixtureTimelineEvent[]): string {
  if (!player.athleteId) {
    return "Non utilizzato";
  }
  const entered = events.find(
    (event) => event.eventType.toLowerCase() === "subst" && event.relatedAthleteId === player.athleteId,
  );
  if (entered) {
    return `Entrato al ${entered.minuteLabel}`;
  }
  const sentOff = events.find(
    (event) =>
      event.athleteId === player.athleteId &&
      event.eventType.toLowerCase() === "card" &&
      (event.eventDetail ?? "").toLowerCase().includes("red"),
  );
  if (sentOff) {
    return `Espulso dalla panchina al ${sentOff.minuteLabel}`;
  }
  return "Non utilizzato";
}

function BenchList({ players, events, side }: { players: readonly FixtureLineupPlayer[]; events: readonly FixtureTimelineEvent[]; side: string }) {
  if (players.length === 0) {
    return null;
  }
  return (
    <ul className="fa-ds-showcase__stack" data-testid={`fixture-bench-${side}`}>
      {players.map((player) => (
        <li key={pitchPlayerId(player)} data-testid={`fixture-bench-player-${pitchPlayerId(player)}`}>
          <RoleBadge code={player.position} /> {player.shirtNumber !== null ? `${player.shirtNumber}. ` : ""}
          {player.name} — <em>{benchStatusLabel(player, events)}</em>
        </li>
      ))}
    </ul>
  );
}

function LineupBlock({
  lineup,
  events,
  side,
}: {
  lineup: FixtureLineup | null;
  events: readonly FixtureTimelineEvent[];
  side: string;
}) {
  if (lineup === null) {
    return (
      <section data-testid={`fixture-lineup-${side}`}>
        <UiStatePanel
          state="empty"
          title="Formazione non disponibile"
          message="La formazione ufficiale non è ancora stata pubblicata per questa squadra."
          testId={`fixture-lineup-empty-${side}`}
        />
      </section>
    );
  }

  const badgesByAthlete = realMatchBadgesByAthlete(events);
  const positions = layoutFromGrid(
    lineup.starters.map((player) => ({ id: pitchPlayerId(player), grid: player.grid })),
  );
  const title = [lineup.clubName, lineup.formation, lineup.coachName ? `All. ${lineup.coachName}` : null]
    .filter(Boolean)
    .join(" · ");

  return (
    <section data-testid={`fixture-lineup-${side}`}>
      <FootballPitch
        title={title}
        players={toPitchPlayers(lineup.starters, badgesByAthlete)}
        positions={positions}
        pitchAriaLabel={`Titolari ${lineup.clubName}`}
      />
      <h4>Panchina</h4>
      <BenchList players={lineup.bench} events={events} side={side} />
    </section>
  );
}

function eventSide(event: FixtureTimelineEvent, detail: FixtureLiveDetail): "home" | "away" | null {
  if (!event.clubId) {
    return null;
  }
  if (event.clubId === detail.homeClubId) {
    return "home";
  }
  if (event.clubId === detail.awayClubId) {
    return "away";
  }
  return null;
}

function eventVisual(event: FixtureTimelineEvent): { icon: ReactNode; headline: ReactNode; detail?: ReactNode } {
  const type = event.eventType.toLowerCase();
  const detailText = (event.eventDetail ?? "").toLowerCase();
  const isOwnGoal = event.scoringKind === "own_goal" || detailText.includes("own");

  if (type === "goal") {
    if (isOwnGoal) {
      return { icon: <OwnGoalIcon />, headline: <>{event.athleteName ?? "?"} (autogol)</> };
    }
    const isMissed = event.scoringKind === "penalty_missed" || detailText.includes("missed");
    if (isMissed) {
      return { icon: <PenaltyMissedIcon />, headline: <>{event.athleteName ?? "?"} — rigore sbagliato</> };
    }
    const isPenalty = event.scoringKind === "penalty_scored" || detailText.includes("penalty");
    return {
      icon: isPenalty ? <PenaltyIcon /> : <GoalIcon />,
      headline: <>{event.athleteName ?? "?"}{isPenalty ? " (rigore)" : ""}</>,
      detail: event.relatedAthleteName ? (
        <>
          <AssistIcon size={12} /> Assist: {event.relatedAthleteName}
        </>
      ) : undefined,
    };
  }
  if (event.scoringKind === "penalty_saved" || type === "penalty_saved") {
    return {
      icon: <PenaltyIcon />,
      headline: <>Rigore parato{event.athleteName ? ` — ${event.athleteName}` : ""}</>,
    };
  }
  if (type === "card") {
    const isRed = detailText.includes("red");
    return { icon: isRed ? <RedCardIcon /> : <YellowCardIcon />, headline: <>{event.athleteName ?? "?"}</> };
  }
  if (type === "subst") {
    return {
      icon: <SubstitutionOutIcon />,
      headline: <>{event.athleteName ?? "?"}</>,
      detail: event.relatedAthleteName ? (
        <>
          <SubstitutionInIcon size={12} /> {event.relatedAthleteName}
        </>
      ) : undefined,
    };
  }
  if (type === "var") {
    return {
      icon: <VarIcon />,
      headline: <>VAR — {event.eventDetail ?? "Revisione"}</>,
      detail: event.athleteName ?? undefined,
    };
  }
  return { icon: undefined, headline: <>{event.eventType}{event.eventDetail ? ` (${event.eventDetail})` : ""}</> };
}

/** Timeline verticale con marcatori di periodo e punteggio progressivo (§9-§12). */
function buildTimelineEntries(detail: FixtureLiveDetail): TimelineEntry[] {
  const entries: TimelineEntry[] = [];
  let homeScore = 0;
  let awayScore = 0;
  let insertedHalftime = false;
  const hasFirstHalf = detail.events.some((e) => (e.minuteElapsed ?? 0) <= 45);
  const hasSecondHalf = detail.events.some((e) => (e.minuteElapsed ?? 0) > 45);

  if (detail.events.length > 0) {
    entries.push({ type: "marker", id: "start", label: "Inizio partita" });
  }

  for (const event of detail.events) {
    if (!insertedHalftime && hasFirstHalf && hasSecondHalf && (event.minuteElapsed ?? 0) > 45) {
      entries.push({ type: "marker", id: "halftime", label: `Intervallo · ${homeScore}-${awayScore}` });
      insertedHalftime = true;
    }

    const side = eventSide(event, detail);
    const detailText = (event.eventDetail ?? "").toLowerCase();
    const isOwnGoal = event.scoringKind === "own_goal" || detailText.includes("own");
    const isMissed = event.scoringKind === "penalty_missed" || detailText.includes("missed");
    const isGoal = event.eventType.toLowerCase() === "goal" && !isMissed;
    if (isGoal && side) {
      const scoringSide = isOwnGoal ? (side === "home" ? "away" : "home") : side;
      if (scoringSide === "home") {
        homeScore += 1;
      } else {
        awayScore += 1;
      }
    }

    if (!side) {
      continue;
    }
    const visual = eventVisual(event);
    entries.push({
      type: "event",
      id: event.id,
      side,
      minuteLabel: event.minuteLabel,
      icon: visual.icon,
      headline: visual.headline,
      detail: visual.detail,
    });
  }

  if (mapFixtureMatchStatus(detail.statusShort) === "finished") {
    entries.push({ type: "marker", id: "end", label: `Fine partita · ${homeScore}-${awayScore}` });
  }

  return entries;
}

export function FixtureDetailBody({ detail }: { detail: FixtureLiveDetail }) {
  const matchStatus = mapFixtureMatchStatus(detail.statusShort);
  const isFinished = matchStatus === "finished";
  const isLive = matchStatus === "live";

  return (
    <div className="fa-ds-showcase__stack" data-testid="fixture-detail">
      <p>
        {detail.homeClubLogoUrl ? (
          <img className="fa-match-card__team-logo" src={detail.homeClubLogoUrl} alt="" aria-hidden="true" />
        ) : null}{" "}
        <strong>{detail.homeClubName}</strong>{" "}
        <span data-testid="fixture-score">
          {detail.homeGoals ?? "—"} – {detail.awayGoals ?? "—"}
        </span>{" "}
        <strong>{detail.awayClubName}</strong>{" "}
        {detail.awayClubLogoUrl ? (
          <img className="fa-match-card__team-logo" src={detail.awayClubLogoUrl} alt="" aria-hidden="true" />
        ) : null}
      </p>
      <p>
        <Badge
          variant={isFinished ? "success" : "accent"}
          className={isLive ? "fa-live-badge" : undefined}
          data-testid="fixture-status"
        >
          {statusLabel(detail.statusShort, detail.statusElapsed)}
        </Badge>{" "}
        {/* A partita finita "Aggiornato" non aggiunge informazione: si mostra solo mentre conta sapere quanto fidarsi del dato (§13). */}
        {!isFinished ? (
          <Badge variant={FEED_VARIANTS[detail.feedState]} data-testid="fixture-feed-state">
            {detail.feedStateLabel}
          </Badge>
        ) : null}
      </p>
      <p>
        {detail.competitionName ? `${detail.competitionName} · ` : ""}
        Inizio: {formatKickoff(detail.kickoffAt)}
      </p>
      {detail.venueName || detail.referee ? (
        <p data-testid="fixture-venue-referee">
          {detail.venueName ? `${detail.venueName}${detail.venueCity ? ` (${detail.venueCity})` : ""}` : ""}
          {detail.venueName && detail.referee ? " · " : ""}
          {detail.referee ? `Arbitro: ${detail.referee}` : ""}
        </p>
      ) : null}

      <div className="fa-pitch-row">
        <LineupBlock lineup={detail.homeLineup} events={detail.events} side="home" />
        <LineupBlock lineup={detail.awayLineup} events={detail.events} side="away" />
      </div>

      <section aria-labelledby="fixture-timeline-title">
        <h3 id="fixture-timeline-title">Cronologia</h3>
        {detail.events.length === 0 ? (
          <UiStatePanel
            state="empty"
            title="Nessun evento"
            message="Il provider non ha ancora pubblicato eventi per questa partita."
            testId="fixture-timeline-empty"
          />
        ) : (
          <MatchTimeline
            homeLabel={detail.homeClubName}
            awayLabel={detail.awayClubName}
            entries={buildTimelineEntries(detail)}
          />
        )}
      </section>
    </div>
  );
}

/** Dettaglio partita del turno europeo (EP13-P04). */
export function FixtureDetailPage() {
  const { can } = useAuth();
  const { pathname } = useLocation();
  const segments = pathname.split("/").filter(Boolean);
  // /turni/:turnId/partite/:fixtureId
  const turnId = segments[1] ?? null;
  const fixtureId = segments[3] ?? null;

  const [detail, setDetail] = useState<FixtureLiveDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const { activeLeagueId } = useAuth();

  const load = useCallback(async () => {
    if (!activeLeagueId || !turnId || !fixtureId) {
      setLoading(false);
      setDetail(null);
      return;
    }
    const stored = loadStoredSession();
    if (!stored?.accessToken) {
      setLoading(false);
      setError("Sessione non disponibile. Accedi di nuovo.");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      setDetail(await fetchFixtureLiveDetail(stored.accessToken, activeLeagueId, turnId, fixtureId));
    } catch (err) {
      setError(getApiErrorMessage(err, "Impossibile caricare la partita."));
      setDetail(null);
    } finally {
      setLoading(false);
    }
  }, [activeLeagueId, fixtureId, turnId]);

  useEffect(() => {
    void load();
  }, [load]);

  useLiveFixturePolling(activeLeagueId, turnId, fixtureId, detail, setDetail, !loading && !error);

  if (!can(["matchday:view"])) {
    return (
      <PageContainer title="Partita">
        <UiStatePanel
          state="forbidden"
          title="Permessi insufficienti"
          message="Non hai accesso ai turni di questa lega."
          testId="fixture-forbidden"
        />
      </PageContainer>
    );
  }

  return (
    <PageContainer
      title={detail ? `${detail.homeClubName} – ${detail.awayClubName}` : "Partita"}
      header={
        <Breadcrumb
          items={[
            { label: "Le mie leghe", href: "/leghe" },
            { label: "Turni", href: "/turni" },
            { label: "Partita" },
          ]}
        />
      }
    >
      <p>
        <Link to="/turni" data-testid="fixture-back">
          Torna ai turni
        </Link>
      </p>

      {loading ? (
        <UiStatePanel
          state="loading"
          title="Caricamento partita"
          message="Recupero formazioni ed eventi…"
          testId="fixture-loading"
        />
      ) : null}

      {!loading && error ? (
        <div data-testid="fixture-error-wrap">
          <UiStatePanel state="error" title="Partita non disponibile" message={error} testId="fixture-error" />
          <Button type="button" variant="secondary" onClick={() => void load()}>
            Riprova
          </Button>
        </div>
      ) : null}

      {!loading && !error && detail ? <FixtureDetailBody detail={detail} /> : null}
    </PageContainer>
  );
}
