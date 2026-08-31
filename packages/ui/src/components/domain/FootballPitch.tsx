import type { MatchBadge, PitchPosition } from "@fantappero/contracts";
import { type HTMLAttributes } from "react";
import { classNames } from "../../utils/classNames.js";
import { EventBadges } from "./EventBadges.js";
import { RoleBadge } from "./RoleBadge.js";

export type PitchPlayer = {
  id: string;
  shirtNumber?: number | null;
  name: string;
  /** Codice ruolo (G/D/M/F o P/D/C/A), passato a `RoleBadge`. */
  role: string | null;
  badges?: readonly MatchBadge[];
  /** Punteggio da mostrare sulla pill (fantasy): `"7.5"` o `"7.5 LIVE"`. */
  scoreLabel?: string | null;
  /** Foto dal provider, quando disponibile; altrimenti resta il cerchio con il numero. */
  photoUrl?: string | null;
};

export type FootballPitchProps = HTMLAttributes<HTMLDivElement> & {
  title: string;
  players: readonly PitchPlayer[];
  positions: readonly PitchPosition[];
  pitchAriaLabel?: string;
};

function abbreviateName(name: string): string {
  const parts = name.trim().split(/\s+/);
  if (parts.length <= 1) {
    return name;
  }
  const last = parts[parts.length - 1] ?? name;
  const initials = parts.slice(0, -1).map((part) => `${part.charAt(0)}.`);
  return `${initials.join(" ")} ${last}`;
}

function PlayerPill({ player }: { player: PitchPlayer }) {
  return (
    <div className="fa-pitch-player" data-testid={`pitch-player-${player.id}`}>
      <div className="fa-pitch-player__badges">
        <EventBadges badges={player.badges ?? []} size={12} />
      </div>
      <div className="fa-pitch-player__card">
        {player.photoUrl ? (
          <img className="fa-pitch-player__photo" src={player.photoUrl} alt="" aria-hidden="true" />
        ) : player.shirtNumber != null ? (
          <span className="fa-pitch-player__number">{player.shirtNumber}</span>
        ) : null}
        {player.photoUrl && player.shirtNumber != null ? (
          <span className="fa-pitch-player__number-badge">{player.shirtNumber}</span>
        ) : null}
        <RoleBadge code={player.role} className="fa-pitch-player__role" />
      </div>
      <span className="fa-pitch-player__name">{abbreviateName(player.name)}</span>
      {player.scoreLabel ? (
        <span className="fa-pitch-player__score">{player.scoreLabel}</span>
      ) : null}
    </div>
  );
}

/**
 * Rappresentazione grafica del campo (EP13-P04-quater §2/§4): rettangolo,
 * linea di metà campo, cerchio centrale, aree di rigore in puro CSS —
 * nessuna immagine, nessuna nuova dipendenza. I giocatori sono posizionati
 * dalle coordinate già calcolate da `layoutFromGrid`/`layoutFromModule`
 * (`packages/contracts/pitch.ts`), condivise con l'app mobile.
 */
export function FootballPitch({
  title,
  players,
  positions,
  pitchAriaLabel,
  className,
  ...rest
}: FootballPitchProps) {
  const positionById = new Map(positions.map((position) => [position.id, position]));
  return (
    <div className={classNames("fa-pitch-wrap", className)} data-testid="football-pitch" {...rest}>
      <h3 className="fa-pitch-wrap__title">{title}</h3>
      <div className="fa-pitch" role="list" aria-label={pitchAriaLabel}>
        <div className="fa-pitch__halfway-line" aria-hidden="true" />
        <div className="fa-pitch__center-circle" aria-hidden="true" />
        <div className="fa-pitch__box fa-pitch__box--top" aria-hidden="true" />
        <div className="fa-pitch__box fa-pitch__box--bottom" aria-hidden="true" />
        {players.map((player) => {
          const position = positionById.get(player.id);
          if (!position) {
            return null;
          }
          return (
            <div
              key={player.id}
              role="listitem"
              className="fa-pitch__slot"
              style={{ left: `${position.xPercent}%`, top: `${position.yPercent}%` }}
            >
              <PlayerPill player={player} />
            </div>
          );
        })}
      </div>
    </div>
  );
}
