import type {
  AiLineupRun,
  H2HCalendar,
  H2HCalendarMatchup,
  H2HCalendarRound,
} from "@fantappero/contracts";
import {
  H2H_GOALS_LABEL,
  H2H_POINTS_LABEL,
  describeH2HResult,
  h2hResultAriaLabel,
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
  aiLineupBusy?: boolean;
  aiLineupRun?: AiLineupRun | null;
  aiLineupError?: string | null;
  onGenerateAiLineups?: (roundId: string) => void;
  onRetry: () => void;
};

const AI_OUTCOME_LABEL: Record<string, string> = {
  created: "Formazione creata",
  updated: "Formazione aggiornata",
  unchanged: "Formazione già valida",
  skipped_locked: "Formazione bloccata, nessuna modifica",
  skipped_manual: "Formazione manuale preservata",
  incomplete: "Formazione non generata",
};

const KICKOFF_FORMATTER = new Intl.DateTimeFormat("it-IT", {
  dateStyle: "short",
  timeStyle: "short",
});

/** Riga temporale della card: quando il risultato è stato calcolato. */
function computedAtLabel(computedAt: string | null | undefined): string {
  if (!computedAt) {
    return "Risultato non ancora calcolato";
  }
  const parsed = new Date(computedAt);
  if (Number.isNaN(parsed.getTime())) {
    return "Risultato non ancora calcolato";
  }
  return `Calcolato il ${KICKOFF_FORMATTER.format(parsed)}`;
}

/** Prima giornata non ancora conclusa; se tutte finite, l'ultima. */
export function resolveDefaultH2HRound(calendar: H2HCalendar): number {
  for (const round of calendar.rounds) {
    if (round.beforeLeagueCreation || round.homologationStatus === "homologated") {
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
  if (round.beforeLeagueCreation) {
    return "Lega creata dopo questo turno";
  }
  if (round.homologationStatus === "homologated") {
    return "Risultati finali (storico)";
  }
  const played = round.matchups.filter((matchup) => !matchup.isBye);
  if (played.some((matchup) => matchup.live)) {
    return "LIVE / risultati provvisori";
  }
  const hasResult = played.some((matchup) => matchup.result != null);
  if (hasResult) {
    return "Risultati provvisori / in attesa";
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
  const display = describeH2HResult(matchup.result);
  const status =
    display.status === "final" ? "finished" : matchup.live ? "live" : "scheduled";
  const statusLabel = matchup.live
    ? "LIVE / provvisorio"
    : display.status === "provisional"
      ? "Provvisorio / in attesa"
      : display.statusLabel;

  return (
    <div className="fa-matchday-matchup" data-testid={`h2h-matchup-${matchup.slotId}`}>
      <Link
        to={`/turni/scontro/${matchup.slotId}`}
        className="fa-matchday-matchup-link"
        data-testid={`h2h-matchup-link-${matchup.slotId}`}
        aria-label={h2hResultAriaLabel(display, homeName, awayName)}
      >
        <MatchCard
          homeTeam={homeName}
          awayTeam={awayName}
          kickoffLabel={computedAtLabel(matchup.result?.computedAt)}
          status={status}
          statusLabel={statusLabel}
          contextLabel="Scontro H2H"
          score={
            display.goalsAvailable && matchup.result
              ? {
                  home: matchup.result.homeFantasyGoals as number,
                  away: matchup.result.awayFantasyGoals as number,
                }
              : null
          }
        />
        <H2HScoreLines display={display} slotId={matchup.slotId} />
      </Link>
    </div>
  );
}

/**
 * Le due grandezze nominate esplicitamente (EP13-P02): il numero grande della
 * MatchCard sono i Gol fantasy, ma da solo resta anonimo.
 */
function H2HScoreLines({
  display,
  slotId,
}: {
  display: ReturnType<typeof describeH2HResult>;
  slotId: string;
}) {
  return (
    <>
      <dl className="fa-h2h-score" data-testid={`h2h-score-${slotId}`}>
        <div className="fa-h2h-score__row">
          <dt className="fa-h2h-score__term">{H2H_GOALS_LABEL}</dt>
          <dd className="fa-h2h-score__value" data-testid={`h2h-score-goals-${slotId}`}>
            {display.goalsLine}
          </dd>
        </div>
        <div className="fa-h2h-score__row">
          <dt className="fa-h2h-score__term">{H2H_POINTS_LABEL}</dt>
          <dd className="fa-h2h-score__value" data-testid={`h2h-score-points-${slotId}`}>
            {display.pointsLine}
          </dd>
        </div>
      </dl>
      {display.unavailableHint ? (
        <p className="fa-h2h-score__hint" data-testid={`h2h-score-hint-${slotId}`}>
          {display.unavailableHint}
        </p>
      ) : null}
    </>
  );
}

/** Tab Calendario fantallenatori — una giornata alla volta via tendina. */
export function MatchdayH2HPanel({
  calendar,
  loading,
  error,
  liveDegraded,
  canAdmin,
  aiLineupBusy = false,
  aiLineupRun = null,
  aiLineupError = null,
  onGenerateAiLineups = () => undefined,
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
    if (round.beforeLeagueCreation) {
      return {
        value: String(round.roundNumber),
        label: `Giornata ${round.roundNumber} · lega creata dopo`,
      };
    }
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
            {calendar.roundCount} giornate · {calendar.matchupCount} scontri
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

      {canAdmin && activeRound?.fantasyRoundId ? (
        <section data-testid="h2h-ai-admin">
          <h2>Formazioni dei fantallenatori AI</h2>
          <p>
            Genera le formazioni valide delle sole squadre controllate dall’AI per questa
            giornata. Le formazioni umane e quelle già bloccate non vengono modificate.
          </p>
          <Button
            type="button"
            disabled={aiLineupBusy}
            onClick={() => onGenerateAiLineups(activeRound.fantasyRoundId as string)}
            data-testid="h2h-generate-ai-lineups"
          >
            {aiLineupBusy ? "Generazione in corso…" : "Genera formazioni AI"}
          </Button>
          {aiLineupRun?.roundId === activeRound.fantasyRoundId ? (
            <div data-testid="h2h-ai-result">
              <p>{aiLineupRun.summary}</p>
              {aiLineupRun.teams.length > 0 ? (
                <ul>
                  {aiLineupRun.teams.map((team) => (
                    <li key={team.fantasyTeamId}>
                      <strong>{team.fantasyTeamName || team.fantasyTeamId}</strong>: {" "}
                      {AI_OUTCOME_LABEL[team.outcome] ?? team.outcome}
                      {team.message ? ` — ${team.message}` : ""}
                    </li>
                  ))}
                </ul>
              ) : null}
            </div>
          ) : null}
          {aiLineupError ? (
            <UiStatePanel
              state="error"
              title="Formazioni AI non generate"
              message={aiLineupError}
              testId="h2h-ai-error"
            />
          ) : null}
        </section>
      ) : null}

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
          {activeRound.beforeLeagueCreation ? (
            <UiStatePanel
              state="empty"
              title="Lega creata dopo questo turno"
              message="Questo turno europeo è già trascorso al momento della creazione della lega: non ospita scontri fantasy."
              testId="h2h-round-before-creation"
            />
          ) : (
            <div className="fa-matchday-matchups">
              {activeRound.matchups.map((matchup) => (
                <MatchupRow key={matchup.slotId} matchup={matchup} />
              ))}
            </div>
          )}
        </section>
      ) : null}
    </div>
  );
}
