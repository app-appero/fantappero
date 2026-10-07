/**
 * Logica pura condivisa web/mobile per l'asta a rilanci (EP08-09), sullo
 * stesso principio di ``pitch.ts``: qui vive UNA sola implementazione del
 * calcolo "rilancio minimo successivo" e del countdown, usata identica dalle
 * due app invece di essere duplicata.
 *
 * Solo per il feedback immediato in UI (es. disabilitare il pulsante di
 * rilancio sotto la soglia, mostrare il countdown): il server resta sempre
 * l'autorità finale su ogni scrittura — le controparti Python autoritative
 * sono ``backend/src/market/live_validators.py`` e ``live_windows.py``.
 */

/** Importo minimo valido per il prossimo rilancio su un lotto. */
export function computeMinimumNextBid(
  currentAmountCredits: number,
  hasLeader: boolean,
  minIncrementCredits: number,
): number {
  if (!hasLeader) {
    return minIncrementCredits;
  }
  return currentAmountCredits + minIncrementCredits;
}

/** Secondi residui prima della chiusura del lotto, mai negativi. */
export function secondsRemaining(closesAtIso: string, nowIso: string): number {
  const closesAt = Date.parse(closesAtIso);
  const now = Date.parse(nowIso);
  return Math.max(0, Math.round((closesAt - now) / 1000));
}

/** Se un rilancio piazzato ora ricadrebbe nella finestra di soft-close. */
export function shouldTriggerSoftClose(
  closesAtIso: string,
  nowIso: string,
  softCloseSeconds: number,
): boolean {
  return secondsRemaining(closesAtIso, nowIso) <= softCloseSeconds;
}

/** Colori dei posti al tavolo: distinti fra loro e dal piano verde. */
export const LIVE_SEAT_ME_COLOR = "#5a8df2";
export const LIVE_SEAT_CALL_COLOR = "#f0c040";
export const LIVE_SEAT_LEAD_COLOR = "#ff5c93";

export const LIVE_SEAT_LEGEND = [
  { id: "me", label: "Tu", color: LIVE_SEAT_ME_COLOR },
  { id: "call", label: "Tocca a lui / ha chiamato", color: LIVE_SEAT_CALL_COLOR },
  { id: "lead", label: "In testa (rilancio)", color: LIVE_SEAT_LEAD_COLOR },
] as const;

/** Stato luminoso di un posto, oltre al segnale «Tu». */
export type LiveSeatCue = "turn" | "caller" | "leader";

export type LiveTurnSeat = {
  fantasyTeamId: string;
  position: number;
};

export type LiveSeatLot = {
  sequenceNumber: number;
  currentLeaderTeamId: string | null;
};

/**
 * Chi ha chiamato il lotto aperto, in modalità a turno.
 *
 * Il server avanza `currentTurnTeamId` appena il lotto si apre (il conteggio
 * include già quel lotto), quindi «a chi tocca» durante il lotto sarebbe il
 * prossimo chiamante. Il chiamante di questo lotto è la posizione precedente
 * nell'ordine estratto: sequenza 1 → posizione 0.
 */
export function resolveLiveLotCallerTeamId(
  turnOrder: readonly LiveTurnSeat[],
  sequenceNumber: number,
): string | null {
  if (turnOrder.length === 0 || sequenceNumber < 1) {
    return null;
  }
  const ordered = [...turnOrder].sort((left, right) => left.position - right.position);
  const index = (sequenceNumber - 1) % ordered.length;
  return ordered[index]?.fantasyTeamId ?? null;
}

export function resolveLiveSeatCue(input: {
  teamId: string;
  currentTurnTeamId?: string | null;
  currentLot: LiveSeatLot | null;
  nominationMode?: string | null;
  turnOrder?: readonly LiveTurnSeat[];
}): LiveSeatCue | null {
  if (input.currentLot?.currentLeaderTeamId === input.teamId) {
    return "leader";
  }
  if (input.currentLot && input.nominationMode === "turn_based") {
    const callerId = resolveLiveLotCallerTeamId(input.turnOrder ?? [], input.currentLot.sequenceNumber);
    if (callerId === input.teamId) {
      return "caller";
    }
  }
  if (!input.currentLot && input.currentTurnTeamId === input.teamId) {
    return "turn";
  }
  return null;
}

export function liveSeatCueColor(cue: LiveSeatCue | null): string | null {
  if (cue === "leader") {
    return LIVE_SEAT_LEAD_COLOR;
  }
  if (cue === "caller" || cue === "turn") {
    return LIVE_SEAT_CALL_COLOR;
  }
  return null;
}

export function liveSeatCueLabel(cue: LiveSeatCue | null, isMe: boolean): string | null {
  if (cue === "leader") {
    return "In testa";
  }
  if (cue === "caller") {
    return "Ha chiamato";
  }
  if (cue === "turn") {
    return isMe ? "Tocca a te" : "Tocca a lui";
  }
  return null;
}

/** Alone del posto: il «Tu» resta visibile anche sopra turno o rilancio. */
export function liveSeatGlow(cue: LiveSeatCue | null, isMe: boolean): string | undefined {
  const layers: string[] = [];
  if (isMe) {
    layers.push("0 0 0 3px rgba(90, 141, 242, 0.55)", "0 0 14px rgba(90, 141, 242, 0.95)");
  }
  if (cue === "turn" || cue === "caller") {
    layers.push("0 0 0 3px rgba(240, 192, 64, 0.65)", "0 0 16px rgba(240, 192, 64, 0.95)");
  }
  if (cue === "leader") {
    layers.push("0 0 0 3px rgba(255, 92, 147, 0.7)", "0 0 18px rgba(255, 92, 147, 0.95)");
  }
  return layers.length > 0 ? layers.join(", ") : undefined;
}
