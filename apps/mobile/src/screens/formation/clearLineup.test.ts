import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
  benchAfterStarterPick,
  benchShortfall,
  clearLineupKeepingLocked,
  restoreBenchActiveRoles,
} from "./benchQuota.ts";
import {
  CLEAR_LINEUP_CONFIRM_POINTS,
  CLEAR_LINEUP_CONFIRM_TITLE,
  clearLineupConfirmMessage,
  clearLineupSuccessMessage,
} from "./clearLineup.ts";

// «Svuota formazione» (Rosario, 20/11). Rosa da 25 in ordine di rosa (P→D→C→A), 4-3-3 salvato.
type Role = "P" | "D" | "C" | "A";
const ids = (prefix: string, count: number) => Array.from({ length: count }, (_, i) => `${prefix}${i + 1}`);
const ROSTER = [...ids("P", 3), ...ids("D", 8), ...ids("C", 8), ...ids("A", 6)];
const ROLE: Record<string, string> = Object.fromEntries(ROSTER.map((id) => [id, id[0] as string]));
const STARTERS = ["P1", "D1", "D2", "D3", "D4", "C1", "C2", "C3", "A1", "A2", "A3"];
const SAVED_BENCH = ["P2", "D5", "D6", "D7", "C4", "C5", "C6", "A4", "A5", "A6", "P3", "D8", "C7", "C8"];
const players = (list: readonly string[]) => list.map((athleteId) => ({ athleteId, role: athleteId[0] as Role }));

function clear(locked: readonly string[] = [], extra: Partial<Parameters<typeof clearLineupKeepingLocked>[0]> = {}) {
  return clearLineupKeepingLocked({
    starterIds: STARTERS,
    benchIds: SAVED_BENCH,
    rosterAthleteIds: ROSTER,
    lockedAthleteIds: locked,
    roleByAthleteId: ROLE,
    ...extra,
  });
}

describe("«Svuota formazione» nell'app", () => {
  it("senza bloccati toglie tutti i titolari e rimette la panchina nell'ordine della rosa", () => {
    const cleared = clear();

    assert.deepEqual(cleared.starterIds, STARTERS.map(() => ""));
    assert.deepEqual(cleared.benchIds, [
      "P1", "D1", "D2", "D3", "C1", "C2", "C3", "A1", "A2", "A3",
      "P2", "P3", "D4", "D5", "D6", "D7", "D8", "C4", "C5", "C6", "C7", "C8", "A4", "A5", "A6",
    ]);
    assert.deepEqual(benchShortfall(players(cleared.benchIds)), {});
    assert.deepEqual(cleared.heldBenchIds, []);
  });

  it("titolari e panchinari bloccati restano al loro posto, il resto si toglie", () => {
    // A3 titolare e D7 (4° in panchina) hanno già giocato.
    const cleared = clear(["A3", "D7"]);

    assert.deepEqual(cleared.starterIds, ["", "", "", "", "", "", "", "", "", "", "A3"]);
    assert.deepEqual(cleared.benchIds.slice(0, 4), ["P2", "D5", "D6", "D7"]);
    // Chi è davanti a D7 non può scavalcarlo: resta dov'è (e il messaggio lo dice).
    assert.deepEqual(cleared.heldBenchIds, ["P2", "D5", "D6"]);
    assert.deepEqual(cleared.benchIds.slice(4, 10), ["C1", "C2", "C3", "A1", "A2", "A4"]);
    assert.equal(cleared.benchIds.includes("A3"), false);
    assert.equal(cleared.benchIds.length, ROSTER.length - 1);
  });

  it("con tutti bloccati non cambia niente", () => {
    const cleared = clear([...STARTERS, ...SAVED_BENCH]);

    assert.deepEqual(cleared.starterIds, STARTERS);
    assert.deepEqual(cleared.benchIds, SAVED_BENCH);
    assert.deepEqual(cleared.heldBenchIds, []);
  });

  it("chi oggi non si può schierare va in coda", () => {
    const cleared = clear([], { unavailableAthleteIds: ["D1", "A1"], unfieldableAthleteIds: ["A1"] });

    assert.deepEqual(cleared.benchIds.slice(0, 10), ["P1", "D2", "D3", "D4", "C1", "C2", "C3", "A2", "A3", "A4"]);
    assert.deepEqual(cleared.benchIds.slice(-2), ["D1", "A1"]);
  });

  it("si ricompone da capo a turno iniziato senza far cambiare posto ai bloccati", () => {
    const locked = ["D7", "A2"];
    const start = clear(locked);
    const starters = [...start.starterIds];
    let bench = [...start.benchIds];
    // D5 e D6 erano davanti a D7: salendo titolari lasciano il posto a D1 e D2, titolari tolti.
    for (const [slot, athleteId] of [[0, "P1"], [1, "D5"], [2, "D6"], [3, "D3"], [4, "D4"], [5, "C1"], [6, "C2"], [7, "C3"], [8, "A1"], [10, "A3"]] as const) {
      starters[slot] = athleteId;
      bench =
        benchAfterStarterPick({ bench, athleteId, savedBench: SAVED_BENCH, lockedAthleteIds: locked, roleByAthleteId: ROLE }) ??
        bench.filter((id) => id !== athleteId);
    }
    assert.equal(starters.filter(Boolean).length, 11);
    assert.deepEqual(bench.slice(0, 4), ["P2", "D1", "D2", "D7"]);
    bench = restoreBenchActiveRoles(players(bench), locked).bench.map((player) => player.athleteId);
    assert.equal(bench.indexOf("D7"), 3);
    assert.deepEqual(benchShortfall(players(bench)), {});
  });

  it("chi sale da un posto senza bloccati dopo di lui: la panchina scorre come prima", () => {
    const start = clear(["D7"]);
    assert.equal(
      benchAfterStarterPick({ bench: start.benchIds, athleteId: "C1", savedBench: SAVED_BENCH, lockedAthleteIds: ["D7"], roleByAthleteId: ROLE }),
      null,
    );
  });
});

describe("testi di «Svuota formazione»", () => {
  it("la conferma ha la frase e i tre punti", () => {
    assert.equal(CLEAR_LINEUP_CONFIRM_TITLE, "Svuotare la formazione?");
    const message = clearLineupConfirmMessage();
    assert.match(message, /^Tolgo tutti i titolari/);
    for (const point of CLEAR_LINEUP_CONFIRM_POINTS) {
      assert.ok(message.includes(`• ${point}`));
    }
  });

  it("dopo lo svuotamento: i cerchi e «Formazione migliore», e chi resta in panchina se succede", () => {
    assert.equal(
      clearLineupSuccessMessage(0),
      "Formazione svuotata. Scegli i titolari toccando i cerchi, oppure usa «Formazione migliore».",
    );
    assert.match(clearLineupSuccessMessage(3), /davanti a un giocatore già bloccato\.$/);
  });
});
