import type { H2HPlayerScore, H2HSideLineup } from "@fantappero/contracts";
import {
  MAX_AUTOMATIC_SUBSTITUTIONS,
  computeCountdown,
  fantasyBadgesFromBonusMalus,
  cleanDisplayName,
  formatFantasyPoints,
  formatCountdown,
  playerVoteState,
} from "@fantappero/contracts";
import { EventBadges } from "@fantappero/ui";
import { useEffect, useState, type ReactElement } from "react";
import { AthleteName } from "../athletes/AthleteCard";

/** Orologio che scatta ogni secondo, per i countdown ai calci d'inizio. */
export function useNow(intervalMs = 1000): number {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const id = window.setInterval(() => setNow(Date.now()), intervalMs);
    return () => window.clearInterval(id);
  }, [intervalMs]);
  return now;
}

const ROLE_CLASS: Record<string, string> = { P: "gk", D: "def", C: "mid", A: "fwd" };

/** `tra 02:14:10` se la partita reale del giocatore deve ancora iniziare. */
function kickoffCountdown(player: H2HPlayerScore, now: number): string | null {
  if (!player.kickoffAt || player.fixtureStatusLabel !== "Da giocare") {
    return null;
  }
  const parts = computeCountdown(player.kickoffAt, new Date(now));
  if (!parts || (parts.days === 0 && parts.hours === 0 && parts.minutes === 0 && parts.seconds === 0)) {
    return null;
  }
  return `tra ${formatCountdown(parts)}`;
}

export type MatchupRowProps = {
  player: H2HPlayerScore;
  /** Posizione in panchina/tribuna (`1°`…). */
  order?: number;
  dim?: boolean;
  compact?: boolean;
  now: number;
  testIdPrefix: string;
  /** `div` quando la riga sta dentro la griglia della vista affiancata. */
  as?: "li" | "div";
};

/** Riga giocatore: solo blu lampeggiante (in campo ora) e S.V. viola fisso. */
export function MatchupPlayerRow({ player, order, dim, compact, now, testIdPrefix, as = "li" }: MatchupRowProps) {
  const Tag = as;
  const vote = playerVoteState(player);
  const countdown = vote.kind === "pending" ? kickoffCountdown(player, now) : null;
  const badges = fantasyBadgesFromBonusMalus(player.bonusMalus ?? []);
  const className = [
    "fa-mrow",
    compact ? "fa-mrow--compact" : "",
    dim ? "fa-mrow--dim" : "",
    vote.live ? "fa-mrow--live" : "",
    vote.kind === "sv" ? "fa-mrow--sv" : "",
  ]
    .filter(Boolean)
    .join(" ");
  return (
    <Tag className={className} data-testid={`${testIdPrefix}-${player.athleteId}`}>
      {order != null ? <span className="fa-mrow__order">{order}°</span> : null}
      <span className={`fa-mrow__role fa-mrow__role--${ROLE_CLASS[player.role] ?? "gk"}`}>{player.role}</span>
      <span className="fa-mrow__body">
        <span className="fa-mrow__name">
          <AthleteName athleteId={player.athleteId}>{player.name}</AthleteName>
          <EventBadges badges={badges} size={12} />
        </span>
        <span className="fa-mrow__team">{player.realTeamName ?? "Squadra reale non associata"}</span>
        {compact && countdown ? (
          <span className="fa-mrow__countdown fa-mrow__countdown--under" data-testid={`${testIdPrefix}-countdown-${player.athleteId}`}>
            {countdown}
          </span>
        ) : null}
      </span>
      {!compact && countdown ? (
        <span className="fa-mrow__countdown" data-testid={`${testIdPrefix}-countdown-${player.athleteId}`}>
          {countdown}
        </span>
      ) : null}
      {vote.label ? (
        <span
          className={[
            "fa-mrow__vote",
            vote.live ? "fa-mrow__vote--live" : "",
            vote.kind === "provisional" ? "fa-mrow__vote--provisional" : "",
            vote.kind === "sv" ? "fa-mrow__vote--sv" : "",
          ]
            .filter(Boolean)
            .join(" ")}
          data-testid={`${testIdPrefix}-score-${player.athleteId}`}
        >
          {vote.label}
        </span>
      ) : null}
    </Tag>
  );
}

/** Tab Panchina (primi cambi) e Tribuna (oltre i cambi) di una squadra. */
export function BenchTabs({ side, title }: { side: H2HSideLineup; title: string }) {
  const [tab, setTab] = useState<"panchina" | "tribuna">("panchina");
  const now = useNow();
  const panchina = side.bench.slice(0, MAX_AUTOMATIC_SUBSTITUTIONS);
  const tribuna = side.bench.slice(MAX_AUTOMATIC_SUBSTITUTIONS);
  const rows = tab === "panchina" ? panchina : tribuna;
  const offset = tab === "panchina" ? 0 : MAX_AUTOMATIC_SUBSTITUTIONS;
  return (
    <div className="fa-mtabs" data-testid={`matchup-bench-wrap-${title}`}>
      <div className="fa-mtabs__bar" role="tablist" aria-label="Panchina e tribuna">
        {(
          [
            ["panchina", "Panchina", panchina.length],
            ["tribuna", "Tribuna", tribuna.length],
          ] as const
        ).map(([id, label, count]) => (
          <button
            key={id}
            type="button"
            role="tab"
            aria-selected={tab === id}
            className={`fa-mtabs__tab${tab === id ? " fa-mtabs__tab--active" : ""}`}
            onClick={() => setTab(id)}
            data-testid={`matchup-tab-${id}-${title}`}
          >
            {label} <span className="fa-mtabs__count">{count}</span>
          </button>
        ))}
      </div>
      <p className="fa-mtabs__hint">
        {tab === "panchina"
          ? `Entrano al massimo ${MAX_AUTOMATIC_SUBSTITUTIONS} panchinari, nell'ordine e a parità di ruolo.`
          : `Oltre i ${MAX_AUTOMATIC_SUBSTITUTIONS} cambi: restano fuori anche se disponibili.`}
      </p>
      {rows.length === 0 ? (
        <p className="fa-mtabs__empty">{tab === "panchina" ? "Nessun panchinaro." : "Nessuno in tribuna."}</p>
      ) : (
        <ul className="fa-mlist" data-testid={tab === "panchina" ? `matchup-bench-${title}` : `matchup-tribuna-${title}`}>
          {rows.map((player, index) => (
            <MatchupPlayerRow
              key={player.athleteId}
              player={player}
              order={offset + index + 1}
              dim={tab === "tribuna"}
              now={now}
              testIdPrefix="matchup-bench-player"
            />
          ))}
        </ul>
      )}
    </div>
  );
}

const ROLE_ORDER = ["P", "D", "C", "A"];

/** Cella della vista affiancata: nome intero su una riga, voto o countdown sotto. */
function VersusCell({ player, dim, now }: { player: H2HPlayerScore | undefined; dim: boolean; now: number }) {
  if (!player) {
    return <div />;
  }
  const vote = playerVoteState(player);
  const countdown = vote.kind === "pending" ? kickoffCountdown(player, now) : null;
  const badges = fantasyBadgesFromBonusMalus(player.bonusMalus ?? []);
  const className = [
    "fa-vcell",
    dim ? "fa-mrow--dim" : "",
    vote.live ? "fa-mrow--live" : "",
    vote.kind === "sv" ? "fa-mrow--sv" : "",
  ]
    .filter(Boolean)
    .join(" ");
  return (
    <div className={className} data-testid={`matchup-versus-player-${player.athleteId}`}>
      <span className={`fa-mrow__role fa-mrow__role--${ROLE_CLASS[player.role] ?? "gk"} fa-vcell__role`}>{player.role}</span>
      <span className="fa-vcell__main">
      <span className="fa-vcell__name">
        <AthleteName athleteId={player.athleteId}>{cleanDisplayName(player.name)}</AthleteName>
        <EventBadges badges={badges} size={12} />
      </span>
      {vote.label ? (
        <span
          className={[
            "fa-mrow__vote",
            vote.live ? "fa-mrow__vote--live" : "",
            vote.kind === "provisional" ? "fa-mrow__vote--provisional" : "",
            vote.kind === "sv" ? "fa-mrow__vote--sv" : "",
          ]
            .filter(Boolean)
            .join(" ")}
          data-testid={`matchup-versus-score-${player.athleteId}`}
        >
          {vote.label}
        </span>
      ) : countdown ? (
        <span className="fa-vcell__cd" data-testid={`matchup-versus-countdown-${player.athleteId}`}>
          {countdown}
        </span>
      ) : null}
      </span>
    </div>
  );
}

function TeamHead({ side }: { side: H2HSideLineup }) {
  return (
    <div className="fa-versus__head">
      <div className="fa-versus__head-name">
        <strong>{side.teamName ?? side.displayName}</strong>
        <span>{side.module ?? ""}</span>
      </div>
      <span className="fa-versus__head-score">{formatFantasyPoints(side.totalScore)}</span>
    </div>
  );
}

/** Vista affiancata: le rose complete dei due allenatori a confronto; i titolari sempre per ruolo. */
export function RosterVersus({ home, away }: { home: H2HSideLineup; away: H2HSideLineup }) {
  const now = useNow();
  const pair = (key: string, a: H2HPlayerScore | undefined, b: H2HPlayerScore | undefined, dim: boolean) => (
    <div className="fa-versus__row" key={key}>
      <VersusCell player={a} dim={dim} now={now} />
      <VersusCell player={b} dim={dim} now={now} />
    </div>
  );
  const rows: ReactElement[] = [];
  for (const role of ROLE_ORDER) {
    const left = home.starters.filter((p) => p.role === role);
    const right = away.starters.filter((p) => p.role === role);
    for (let i = 0; i < Math.max(left.length, right.length); i += 1) {
      rows.push(pair(`s-${role}-${i}`, left[i], right[i], false));
    }
  }
  const slots = MAX_AUTOMATIC_SUBSTITUTIONS;
  const total = Math.max(home.bench.length, away.bench.length);
  const benchRows: ReactElement[] = [];
  const tribRows: ReactElement[] = [];
  for (let i = 0; i < total; i += 1) {
    (i >= slots ? tribRows : benchRows).push(pair(`b-${i}`, home.bench[i], away.bench[i], i >= slots));
  }
  return (
    <div className="fa-versus" data-testid="matchup-versus">
      <div className="fa-versus__row fa-versus__row--head">
        <TeamHead side={home} />
        <TeamHead side={away} />
      </div>
      <h3 className="fa-versus__title">Titolari</h3>
      {rows}
      {benchRows.length > 0 ? <h3 className="fa-versus__title">Panchina</h3> : null}
      {benchRows}
      {tribRows.length > 0 ? <h3 className="fa-versus__title">Tribuna</h3> : null}
      {tribRows}
    </div>
  );
}
