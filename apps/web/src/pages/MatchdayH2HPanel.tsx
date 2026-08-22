import type {
  H2HCalendar,
  H2HCalendarMatchup,
  H2HCalendarRound,
  H2HMatchupScore,
} from "@fantappero/contracts";
import {
  Badge,
  Button,
  MatchCard,
  Select,
  UiStatePanel,
} from "@fantappero/ui";
import { useEffect, useMemo, useState } from "react";
import { Link } from "../router/simpleRouter";

type Props = {
  calendar: H2HCalendar | null;
  loading: boolean;
  error: string | null;
  liveDegraded: boolean;
  canAdmin: boolean;
  onRetry: () => void;
};

function formatScore(score: number | null): string {
  if (score === null || Number.isNaN(score)) {
    return "—";
  }
  return score.toFixed(1);
}

function resultLabel(result: H2HMatchupScore): string {
  const homeGoals = result.homeFantasyGoals ?? 0;
  const awayGoals = result.awayFantasyGoals ?? 0;
  const points = `${formatScore(result.homeScore)} – ${formatScore(result.awayScore)}`;
  return `${homeGoals}–${awayGoals} (${points})`;
}

/** Prima giornata non ancora conclusa; se tutte finite, l'ultima. */
export function resolveDefaultH2HRound(calendar: H2HCalendar): number {
  for (const round of calendar.rounds) {
    if (round.homologationStatus === "homologated") {
      continue;
    }
    const played = round.matchups.filter((matchup) => !matchup.isBye);
    const allFinal =
      played.length > 0 && played.every((matchup) => matchup.result?.resultFinal === true);
    if (!allFinal) {
      return round.roundNumber;
    }
  }
  const last = calendar.rounds[calendar.rounds.length - 1];
  return last?.roundNumber ?? 1;
}

function roundStatusHint(round: H2HCalendarRound): string {
  if (round.homologationStatus === "homologated") {
    return "Risultati finali (storico)";
  }
  const played = round.matchups.filter((matchup) => !matchup.isBye);
  const hasResult = played.some((matchup) => matchup.result != null);
  if (hasResult) {
    return "Risultati provvisori / in corso";
  }
  if (round.europeanTurnStatus) {
    return `Turno europeo: ${round.europeanTurnStatus}`;
  }
  return "Giornata da disputare";
}

function MatchupRow({ matchup }: { matchup: H2HCalendarMatchup }) {
  const homeName = matchup.homeTeamName ?? matchup.homeDisplayName;
  if (matchup.isBye) {
    return (
      <div className="fa-matchday-matchup" data-testid={`h2h-matchup-${matchup.slotId}`}>
        <MatchCard
          homeTeam={homeName}
          awayTeam="Riposo"
          kickoffLabel="Bye"
          status="scheduled"
          statusLabel="Riposo"
          contextLabel="Scontro H2H"
        />
      </div>
    );
  }

  const awayName = matchup.awayTeamName ?? matchup.awayDisplayName ?? "Avversario";
  const status = matchup.result
    ? matchup.result.resultFinal
      ? "finished"
      : "live"
    : "scheduled";
  const statusLabel = matchup.result
    ? matchup.result.resultFinal
      ? "Finale"
      : "Provvisorio"
    : "In attesa";

  return (
    <div className="fa-matchday-matchup" data-testid={`h2h-matchup-${matchup.slotId}`}>
      <Link
        to={`/turni/scontro/${matchup.slotId}`}
        className="fa-matchday-matchup-link"
        data-testid={`h2h-matchup-link-${matchup.slotId}`}
      >
        <MatchCard
          homeTeam={homeName}
          awayTeam={awayName}
          kickoffLabel={
            matchup.result ? resultLabel(matchup.result) : "Risultato non ancora calcolato"
          }
          status={status}
          statusLabel={statusLabel}
          contextLabel="Scontro H2H"
          score={
            matchup.result &&
            matchup.result.homeFantasyGoals !== null &&
            matchup.result.awayFantasyGoals !== null
              ? {
                  home: matchup.result.homeFantasyGoals,
                  away: matchup.result.awayFantasyGoals,
                }
              : null
          }
        />
      </Link>
    </div>
  );
}

/** Tab Calendario fantallenatori — una giornata alla volta via tendina. */
export function MatchdayH2HPanel({
  calendar,
  loading,
  error,
  liveDegraded,
  canAdmin,
  onRetry,
}: Props) {
  const [selectedRound, setSelectedRound] = useState<number | null>(() =>
    calendar ? resolveDefaultH2HRound(calendar) : null,
  );

  useEffect(() => {
    if (!calendar || calendar.rounds.length === 0) {
      setSelectedRound(null);
      return;
    }
    setSelectedRound((current) => {
      if (current != null && calendar.rounds.some((round) => round.roundNumber === current)) {
        return current;
      }
      return resolveDefaultH2HRound(calendar);
    });
  }, [calendar]);

  const activeRoundNumber = selectedRound ?? (calendar ? resolveDefaultH2HRound(calendar) : null);

  const activeRound = useMemo(() => {
    if (!calendar || activeRoundNumber == null) {
      return null;
    }
    return calendar.rounds.find((round) => round.roundNumber === activeRoundNumber) ?? null;
  }, [calendar, activeRoundNumber]);

  if (loading) {
    return (
      <UiStatePanel
        state="loading"
        title="Caricamento calendario"
        message="Recupero degli scontri tra fantallenatori…"
        testId="h2h-loading"
      />
    );
  }

  if (error) {
    return (
      <div data-testid="h2h-error-wrap">
        <UiStatePanel
          state="error"
          title="Calendario non disponibile"
          message={error}
          testId="h2h-error"
        />
        <Button type="button" variant="secondary" onClick={onRetry}>
          Ricarica
        </Button>
      </div>
    );
  }

  if (!calendar) {
    return (
      <div data-testid="h2h-empty-wrap">
        <UiStatePanel
          state="empty"
          title="Calendario non ancora confermato"
          message={
            canAdmin
              ? "Genera e conferma il calendario scontri diretti in Amministrazione lega."
              : "L'amministratore deve generare e confermare il calendario H2H prima che compaia qui."
          }
          testId="h2h-empty"
        />
        {canAdmin ? (
          <Link to="/lega/amministrazione" data-testid="h2h-admin-link">
            Vai ad Amministrazione lega
          </Link>
        ) : null}
      </div>
    );
  }

  const roundOptions = calendar.rounds.map((round) => {
    const played = round.matchups.filter((matchup) => !matchup.isBye);
    const finals = played.filter((matchup) => matchup.result?.resultFinal).length;
    const suffix =
      round.homologationStatus === "homologated"
        ? " · storico"
        : finals > 0
          ? ` · ${finals}/${played.length} finali`
          : "";
    return {
      value: String(round.roundNumber),
      label: `Giornata ${round.roundNumber}${suffix}`,
    };
  });

  return (
    <div className="fa-matchday-h2h" data-testid="h2h-calendar">
      <header className="fa-matchday-toolbar">
        <div className="fa-matchday-toolbar__meta">
          <p className="fa-matchday-lede">
            Girone di andata · {calendar.roundCount} giornate · {calendar.matchupCount} scontri
            {calendar.byeCount > 0 ? ` · ${calendar.byeCount} riposi` : ""}
          </p>
          <p className="fa-matchday-hint">
            Seleziona una giornata per vedere gli scontri. Le giornate già concluse restano
            disponibili come storico.
          </p>
        </div>
        <Select
          label="Giornata"
          options={roundOptions}
          value={activeRoundNumber != null ? String(activeRoundNumber) : ""}
          onChange={(event) => setSelectedRound(Number(event.target.value))}
          data-testid="h2h-round-select"
        />
        <div className="fa-matchday-toolbar__badges">
          {calendar.live ? (
            <Badge variant="warning" data-testid="h2h-live-badge">
              Aggiornamento live
            </Badge>
          ) : null}
          {liveDegraded ? (
            <span data-testid="h2h-live-degraded" className="fa-matchday-degraded">
              Aggiornamento live rallentato…
            </span>
          ) : null}
        </div>
      </header>

      {activeRound ? (
        <section
          className="fa-matchday-round"
          data-testid={`h2h-round-${activeRound.roundNumber}`}
          aria-labelledby="h2h-round-title"
        >
          <div className="fa-matchday-round__header">
            <h2 id="h2h-round-title">Giornata {activeRound.roundNumber}</h2>
            <Badge
              variant={
                activeRound.homologationStatus === "homologated" ? "success" : "warning"
              }
              data-testid="h2h-round-status"
            >
              {roundStatusHint(activeRound)}
            </Badge>
          </div>
          <div className="fa-matchday-matchups">
            {activeRound.matchups.map((matchup) => (
              <MatchupRow key={matchup.slotId} matchup={matchup} />
            ))}
          </div>
        </section>
      ) : null}
    </div>
  );
}
