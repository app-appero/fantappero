import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { describe, it } from "node:test";
import {
  TURN_DISPLAY_LABEL,
  resolveTurnDisplayStates,
} from "../../../../packages/contracts/src/fantasyTurns.ts";
import { europeanTurnOptionLabel, turnSkipReason } from "./turnLabels.ts";

const REASON = "Soglia non raggiunta: 20 partite eleggibili su 25";

const skipped = { number: 12, status: "skipped", effectiveStatus: "skipped", matchStatus: "scheduled", skipReason: REASON } as const;
const upcoming = { number: 13, status: "scheduled", effectiveStatus: "scheduled", matchStatus: "scheduled", skipReason: null } as const;

describe("Turni europei: motivo del turno saltato (corsa M3, 22/11)", () => {
  it("il turno saltato porta il motivo dell'API", () => {
    const [state] = resolveTurnDisplayStates([skipped]);
    assert.equal(state, "skipped");
    assert.equal(turnSkipReason(skipped, "skipped"), REASON);
  });

  it("nessun motivo per un turno non saltato o senza motivo", () => {
    assert.equal(turnSkipReason(upcoming, "next"), null);
    // Un motivo rimasto su un turno che non è saltato non si mostra.
    assert.equal(turnSkipReason({ skipReason: REASON }, "completed"), null);
    assert.equal(turnSkipReason({ skipReason: "  " }, "skipped"), null);
    assert.equal(turnSkipReason({ skipReason: null }, "skipped"), null);
  });

  it("nel menù dei turni il motivo segue lo stato", () => {
    assert.equal(
      europeanTurnOptionLabel(skipped, "skipped", TURN_DISPLAY_LABEL),
      `Turno 12 — Turno saltato (${REASON})`,
    );
    assert.equal(europeanTurnOptionLabel(upcoming, "next", TURN_DISPLAY_LABEL), "Turno 13 — Prossimo");
  });

  it("la schermata Turni usa il motivo nel menù e nel dettaglio", () => {
    const source = readFileSync(new URL("../screens/MatchdayScreen.tsx", import.meta.url), "utf8");
    assert.match(source, /europeanTurnOptionLabel\(turn, turnDisplayStates\[index\] \?\? "upcoming", TURN_DISPLAY_LABEL\)/);
    assert.match(source, /turnSkipReason\(selected, selectedDisplayState\)/);
    assert.match(source, /testID="matchday-turn-skip-reason"/);
  });
});
