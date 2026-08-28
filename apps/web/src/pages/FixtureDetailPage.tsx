import type { FixtureLineup, FixtureLiveDetail, ProviderFeedState } from "@fantappero/contracts";
import { mapFixtureMatchStatus } from "@fantappero/contracts";
import { Badge, Breadcrumb, Button, PageContainer, UiStatePanel } from "@fantappero/ui";
import { useCallback, useEffect, useState } from "react";
import { fetchFixtureLiveDetail } from "../api/leagues";
import { getApiErrorMessage, useAuth } from "../auth/AuthContext";
import { loadStoredSession } from "../auth/sessionStorage";
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
  return Number.isNaN(parsed.getTime())
    ? "Orario non disponibile"
    : KICKOFF_FORMAT.format(parsed);
}

function LineupBlock({ lineup, side }: { lineup: FixtureLineup | null; side: string }) {
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

  return (
    <section data-testid={`fixture-lineup-${side}`}>
      <h3>
        {lineup.clubName}
        {lineup.formation ? ` · ${lineup.formation}` : ""}
      </h3>
      <h4>Titolari</h4>
      <ul data-testid={`fixture-starters-${side}`}>
        {lineup.starters.map((player) => (
          <li key={`${player.athleteId ?? player.name}-${player.shirtNumber ?? ""}`}>
            {player.shirtNumber !== null ? `${player.shirtNumber}. ` : ""}
            {player.name}
            {player.position ? ` (${player.position})` : ""}
          </li>
        ))}
      </ul>
      {lineup.bench.length > 0 ? (
        <>
          <h4>Panchina</h4>
          <ul data-testid={`fixture-bench-${side}`}>
            {lineup.bench.map((player) => (
              <li key={`${player.athleteId ?? player.name}-${player.shirtNumber ?? ""}`}>
                {player.shirtNumber !== null ? `${player.shirtNumber}. ` : ""}
                {player.name}
              </li>
            ))}
          </ul>
        </>
      ) : null}
    </section>
  );
}

export function FixtureDetailBody({ detail }: { detail: FixtureLiveDetail }) {
  return (
    <div className="fa-ds-showcase__stack" data-testid="fixture-detail">
      <p>
        <strong>{detail.homeClubName}</strong>{" "}
        <span data-testid="fixture-score">
          {detail.homeGoals ?? "—"} – {detail.awayGoals ?? "—"}
        </span>{" "}
        <strong>{detail.awayClubName}</strong>
      </p>
      <p>
        <Badge
          variant={mapFixtureMatchStatus(detail.statusShort) === "finished" ? "success" : "accent"}
          data-testid="fixture-status"
        >
          {statusLabel(detail.statusShort, detail.statusElapsed)}
        </Badge>{" "}
        <Badge variant={FEED_VARIANTS[detail.feedState]} data-testid="fixture-feed-state">
          {detail.feedStateLabel}
        </Badge>
      </p>
      <p>
        {detail.competitionName ? `${detail.competitionName} · ` : ""}
        Inizio: {formatKickoff(detail.kickoffAt)}
      </p>

      <div className="fa-ds-showcase__row" style={{ alignItems: "flex-start" }}>
        <LineupBlock lineup={detail.homeLineup} side="home" />
        <LineupBlock lineup={detail.awayLineup} side="away" />
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
          <ol data-testid="fixture-timeline">
            {detail.events.map((event) => (
              <li key={event.id}>
                <strong>{event.minuteLabel}</strong> — {event.eventType}
                {event.eventDetail ? ` (${event.eventDetail})` : ""}
                {event.athleteName ? `: ${event.athleteName}` : ""}
                {event.relatedAthleteName ? ` — assist ${event.relatedAthleteName}` : ""}
                {event.clubName ? ` · ${event.clubName}` : ""}
              </li>
            ))}
          </ol>
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
          <UiStatePanel
            state="error"
            title="Partita non disponibile"
            message={error}
            testId="fixture-error"
          />
          <Button type="button" variant="secondary" onClick={() => void load()}>
            Riprova
          </Button>
        </div>
      ) : null}

      {!loading && !error && detail ? <FixtureDetailBody detail={detail} /> : null}
    </PageContainer>
  );
}
