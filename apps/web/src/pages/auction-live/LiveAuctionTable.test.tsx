import type { FantasyTeamSummary, LiveLot } from "@fantappero/contracts";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { LiveAuctionTable } from "./LiveAuctionTable";

function team(id: string, name: string): FantasyTeamSummary {
  return {
    id,
    leagueId: "league",
    membershipId: id,
    userId: id,
    userType: "human",
    name,
    rosterSize: 25,
    filledSlots: 0,
    compositionStatus: "incomplete",
  };
}

const LOT: LiveLot = {
  id: "lot",
  sessionId: "session",
  athleteId: "athlete",
  athleteName: "A. Abdi",
  sequenceNumber: 1,
  status: "open",
  openedAt: "2026-10-05T10:00:00.000Z",
  closesAt: "2026-10-05T10:00:10.000Z",
  minIncrementCredits: 1,
  currentLeaderTeamId: "leader",
  currentLeaderTeamName: "In testa",
  currentAmountCredits: 40,
  minimumNextAmountCredits: 41,
  closedAt: null,
};

describe("LiveAuctionTable", () => {
  it("lights me, the caller and the current leader with different cues", () => {
    const html = renderToStaticMarkup(
      createElement(LiveAuctionTable, {
        teams: [team("me", "Io"), team("caller", "Chiamante"), team("leader", "In testa")],
        currentLot: LOT,
        secondsRemaining: 10,
        myTeamId: "me",
        currentTurnTeamId: "next",
        nominationMode: "turn_based",
        turnOrder: [
          { fantasyTeamId: "caller", fantasyTeamName: "Chiamante", position: 0 },
          { fantasyTeamId: "leader", fantasyTeamName: "In testa", position: 1 },
          { fantasyTeamId: "me", fantasyTeamName: "Io", position: 2 },
        ],
      }),
    );

    expect(html).toContain('data-testid="auction-live-seat-me"');
    expect(html).toContain('data-me="true"');
    expect(html).toContain('data-cue="caller"');
    expect(html).toContain('data-cue="leader"');
    expect(html).toContain("Ha chiamato");
    expect(html).toContain("In testa");
    expect(html).toContain('data-testid="auction-live-seat-legend"');
    expect(html).not.toContain('data-cue="turn"');
  });

  it("marks whose turn it is while the table waits for the next call", () => {
    const html = renderToStaticMarkup(
      createElement(LiveAuctionTable, {
        teams: [team("me", "Io"), team("turn", "Di turno")],
        currentLot: null,
        secondsRemaining: null,
        myTeamId: "me",
        currentTurnTeamId: "turn",
        nominationMode: "turn_based",
        turnOrder: [],
      }),
    );

    expect(html).toContain('data-cue="turn"');
    expect(html).toContain("Tocca a lui");
    expect(html).toContain(">Tu<");
  });
});
