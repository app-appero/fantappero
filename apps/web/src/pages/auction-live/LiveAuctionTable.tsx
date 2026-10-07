import type { FantasyTeamSummary, LiveLot, LiveTurnOrderEntry, MarketLiveNominationMode } from "@fantappero/contracts";
import {
  LIVE_SEAT_LEGEND,
  LIVE_SEAT_ME_COLOR,
  liveSeatCueColor,
  liveSeatCueLabel,
  liveSeatGlow,
  resolveLiveSeatCue,
} from "@fantappero/contracts";
import { AthleteName } from "../../athletes/AthleteCard";

function seatPosition(index: number, total: number): { left: string; top: string } {
  const angle = (index / total) * 2 * Math.PI - Math.PI / 2;
  const rx = 46;
  const ry = 42;
  return {
    left: `${50 + rx * Math.cos(angle)}%`,
    top: `${50 + ry * Math.sin(angle)}%`,
  };
}

/**
 * Tavolo dell'asta live: le squadre della lega "sedute" intorno a un piano
 * ovale, con il lotto corrente al centro — stessa idea di un tavolo da
 * poker, senza copiarne le meccaniche (qui non ci sono carte/mani, solo
 * partecipanti e un lotto in evidenza).
 *
 * Tre luci distinte, combinabili: blu = tu, oro = tocca chiamare o ha
 * chiamato il lotto, rosa = in testa al rilancio.
 */
export function LiveAuctionTable({
  teams,
  currentLot,
  secondsRemaining,
  currentTurnTeamId = null,
  myTeamId = null,
  nominationMode = null,
  turnOrder = [],
}: {
  teams: readonly FantasyTeamSummary[];
  currentLot: LiveLot | null;
  secondsRemaining: number | null;
  /** Modalità "a turno": id della squadra a cui tocca chiamare il prossimo lotto. */
  currentTurnTeamId?: string | null;
  myTeamId?: string | null;
  nominationMode?: MarketLiveNominationMode | null;
  turnOrder?: readonly LiveTurnOrderEntry[];
}) {
  if (teams.length === 0) {
    return null;
  }

  return (
    <div className="fa-live-auction-table" data-testid="auction-live-table">
      <div className="fa-live-auction-table__surface">
        <div className="fa-live-auction-table__center">
          {currentLot ? (
            <>
              <p className="fa-live-auction-table__athlete">
                <AthleteName athleteId={currentLot.athleteId}>{currentLot.athleteName}</AthleteName>
              </p>
              <p className="fa-live-auction-table__amount">{currentLot.currentAmountCredits} crediti</p>
              {secondsRemaining !== null ? (
                <p className="fa-live-auction-table__countdown">{secondsRemaining}s</p>
              ) : null}
            </>
          ) : (
            <p className="fa-live-auction-table__waiting">In attesa del prossimo lotto…</p>
          )}
        </div>
        {teams.map((team, index) => {
          const position = seatPosition(index, teams.length);
          const isMe = myTeamId === team.id;
          const cue = resolveLiveSeatCue({
            teamId: team.id,
            currentTurnTeamId,
            currentLot,
            nominationMode,
            turnOrder,
          });
          const cueColor = liveSeatCueColor(cue);
          const borderColor = cueColor ?? (isMe ? LIVE_SEAT_ME_COLOR : undefined);
          const cueLabel = liveSeatCueLabel(cue, isMe);
          const seatClassName = [
            "fa-live-auction-table__seat",
            isMe ? "fa-live-auction-table__seat--me" : null,
            cue ? `fa-live-auction-table__seat--${cue}` : null,
          ]
            .filter(Boolean)
            .join(" ");
          return (
            <div
              key={team.id}
              className={seatClassName}
              style={{ left: position.left, top: position.top }}
              data-testid={`auction-live-seat-${team.id}`}
              data-me={isMe ? "true" : undefined}
              data-cue={cue ?? undefined}
            >
              <div
                className="fa-live-auction-table__avatar"
                style={{
                  borderColor,
                  boxShadow: liveSeatGlow(cue, isMe),
                }}
              >
                {team.name.charAt(0).toUpperCase()}
              </div>
              <span
                className="fa-live-auction-table__seat-name"
                style={{ color: cueColor ?? (isMe ? LIVE_SEAT_ME_COLOR : undefined) }}
              >
                {team.name}
              </span>
              {isMe ? <span className="fa-live-auction-table__you">Tu</span> : null}
              {cueLabel ? <span className="fa-live-auction-table__cue">{cueLabel}</span> : null}
            </div>
          );
        })}
      </div>
      <ul className="fa-live-auction-legend" data-testid="auction-live-seat-legend">
        {LIVE_SEAT_LEGEND.map((item) => (
          <li key={item.id} className="fa-live-auction-legend__item">
            <span className="fa-live-auction-legend__swatch" style={{ backgroundColor: item.color, color: item.color }} />
            {item.label}
          </li>
        ))}
      </ul>
    </div>
  );
}
