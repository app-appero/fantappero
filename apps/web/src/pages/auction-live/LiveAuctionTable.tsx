import type { FantasyTeamSummary, LiveLot } from "@fantappero/contracts";

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
 */
export function LiveAuctionTable({
  teams,
  currentLot,
  secondsRemaining,
}: {
  teams: readonly FantasyTeamSummary[];
  currentLot: LiveLot | null;
  secondsRemaining: number | null;
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
              <p className="fa-live-auction-table__athlete">{currentLot.athleteName}</p>
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
          const isLeader = currentLot?.currentLeaderTeamId === team.id;
          return (
            <div
              key={team.id}
              className={
                isLeader
                  ? "fa-live-auction-table__seat fa-live-auction-table__seat--leading"
                  : "fa-live-auction-table__seat"
              }
              style={{ left: position.left, top: position.top }}
              data-testid={`auction-live-seat-${team.id}`}
            >
              <div className="fa-live-auction-table__avatar">{team.name.charAt(0).toUpperCase()}</div>
              <span className="fa-live-auction-table__seat-name">{team.name}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
