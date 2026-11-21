import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
  CLEAR_LINEUP_CONFIRM_POINTS,
  benchActiveShortfall,
  benchAfterStarterPick,
  clearLineupKeepingLocked,
  clearLineupSuccessMessage,
  evaluateBenchOrderLock,
  evaluateProgressiveLock,
  restoreBenchActiveRoles,
  slotsFromLineupIds,
} from "./fantasyLineups.ts";

// «Svuota formazione» (Rosario, 20/11). Rosa da 25 in ordine di rosa (P→D→C→A), 4-3-3 salvato.
const ids = (prefix: string, count: number) => Array.from({ length: count }, (_, i) => `${prefix}${i + 1}`);
const ROSTER = [...ids("P", 3), ...ids("D", 8), ...ids("C", 8), ...ids("A", 6)];
const ROLE: Record<string, string> = Object.fromEntries(ROSTER.map((id) => [id, id[0] as string]));
const STARTERS = ["P1", "D1", "D2", "D3", "D4", "C1", "C2", "C3", "A1", "A2", "A3"];
const SAVED_BENCH = ["P2", "D5", "D6", "D7", "C4", "C5", "C6", "A4", "A5", "A6", "P3", "D8", "C7", "C8"];
const players = (list: readonly string[]) => list.map((athleteId) => ({ athleteId, role: ROLE[athleteId] as "P" }));

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

describe("clearLineupKeepingLocked", () => {
  it("senza bloccati toglie tutti i titolari e rimette la panchina nell'ordine della rosa", () => {
    const cleared = clear();

    assert.deepEqual(cleared.starterIds, STARTERS.map(() => ""));
    // Tutta la rosa in panchina o in tribuna (il server la vuole completa), primi 10 in quota.
    assert.deepEqual(cleared.benchIds, [
      "P1", "D1", "D2", "D3", "C1", "C2", "C3", "A1", "A2", "A3",
      "P2", "P3", "D4", "D5", "D6", "D7", "D8", "C4", "C5", "C6", "C7", "C8", "A4", "A5", "A6",
    ]);
    assert.deepEqual(benchActiveShortfall(players(cleared.benchIds)), {});
    assert.deepEqual(cleared.heldBenchIds, []);
  });

  it("i titolari bloccati restano nel loro slot, gli altri si tolgono", () => {
    const cleared = clear(["D2", "A3"]);

    assert.deepEqual(cleared.starterIds, ["", "", "D2", "", "", "", "", "", "", "", "A3"]);
    assert.equal(cleared.benchIds.includes("D2"), false);
    assert.equal(cleared.benchIds.includes("A3"), false);
    assert.equal(cleared.benchIds.length, ROSTER.length - 2);
  });

  it("chi è bloccato in panchina resta al suo posto, con chi lo precede; dopo di lui si ricompone", () => {
    // D7 (4° in panchina) ha già giocato: P2, D5 e D6 non possono scavalcarlo.
    const cleared = clear(["D7"]);

    assert.deepEqual(cleared.starterIds, STARTERS.map(() => ""));
    assert.deepEqual(cleared.benchIds.slice(0, 4), ["P2", "D5", "D6", "D7"]);
    assert.deepEqual(cleared.heldBenchIds, ["P2", "D5", "D6"]);
    // Dopo D7 l'ordine della rosa, con i primi 10 in quota: C e A salgono, gli altri in tribuna.
    assert.deepEqual(cleared.benchIds.slice(4, 10), ["C1", "C2", "C3", "A1", "A2", "A3"]);
    assert.deepEqual(benchActiveShortfall(players(cleared.benchIds)), {});
    // Il server non avrebbe niente da ridire: il bloccato non si è mosso.
    assert.deepEqual(
      evaluateBenchOrderLock({
        previousBench: SAVED_BENCH,
        proposedBench: cleared.benchIds,
        lockedAthleteIds: ["D7"],
        roleByAthleteId: ROLE,
      }),
      [],
    );
    assert.deepEqual(
      evaluateProgressiveLock({
        previousSlots: slotsFromLineupIds(STARTERS, SAVED_BENCH),
        proposedSlots: slotsFromLineupIds(cleared.starterIds, cleared.benchIds),
        lockedAthleteIds: ["D7"],
      }),
      [],
    );
  });

  it("un bloccato in tribuna tiene fermi tutti quelli prima di lui", () => {
    const cleared = clear(["C7"]);

    assert.deepEqual(cleared.benchIds.slice(0, SAVED_BENCH.indexOf("C7") + 1), SAVED_BENCH.slice(0, 13));
    assert.deepEqual(cleared.heldBenchIds, SAVED_BENCH.slice(0, 12));
    // I titolari tolti vanno dopo di lui, nell'ordine della rosa.
    assert.deepEqual(cleared.benchIds.slice(13), ["P1", "D1", "D2", "D3", "D4", "C1", "C2", "C3", "C8", "A1", "A2", "A3"]);
  });

  it("con tutti bloccati non cambia niente", () => {
    const everyone = [...STARTERS, ...SAVED_BENCH];
    const cleared = clear(everyone);

    assert.deepEqual(cleared.starterIds, STARTERS);
    assert.deepEqual(cleared.benchIds, SAVED_BENCH);
    assert.deepEqual(cleared.heldBenchIds, []);
  });

  it("chi oggi non si può schierare va in coda, a meno che serva per la quota", () => {
    // D1 squalificato: in coda. A1 senza voto: in coda, e non alza la quota degli attaccanti.
    const cleared = clear([], { unavailableAthleteIds: ["D1", "A1"], unfieldableAthleteIds: ["A1"] });

    assert.deepEqual(cleared.benchIds.slice(0, 10), ["P1", "D2", "D3", "D4", "C1", "C2", "C3", "A2", "A3", "A4"]);
    assert.deepEqual(cleared.benchIds.slice(-2), ["D1", "A1"]);
  });

  it("chi non è nella rosa schierabile (es. in esubero di ruolo) non entra in panchina", () => {
    const cleared = clear([], { rosterAthleteIds: ROSTER.filter((id) => id !== "A6") });
    assert.equal(cleared.benchIds.includes("A6"), false);
    assert.equal(cleared.benchIds.length, ROSTER.length - 1);
  });
});

describe("benchAfterStarterPick", () => {
  // Dopo lo svuotamento con D7 bloccato al 4° posto: P2, D5, D6, D7, poi il resto.
  const cleared = clear(["D7"]);

  it("chi sale da davanti a un bloccato lascia il posto a un pari ruolo tolto dai titolari", () => {
    const next = benchAfterStarterPick({
      bench: cleared.benchIds,
      athleteId: "D5",
      savedBench: SAVED_BENCH,
      lockedAthleteIds: ["D7"],
      roleByAthleteId: ROLE,
    });

    assert.ok(next);
    // D1 (titolare tolto) prende il 2° posto di D5: D7 resta 4°.
    assert.deepEqual(next.slice(0, 4), ["P2", "D1", "D6", "D7"]);
    assert.equal(next.includes("D5"), false);
    assert.equal(next.length, cleared.benchIds.length - 1);
    assert.deepEqual(
      evaluateBenchOrderLock({ previousBench: SAVED_BENCH, proposedBench: next, lockedAthleteIds: ["D7"], roleByAthleteId: ROLE }),
      [],
    );
    // Se scorresse, D7 cambierebbe posto e il salvataggio verrebbe rifiutato.
    const shifted = cleared.benchIds.filter((id) => id !== "D5");
    assert.equal(
      evaluateBenchOrderLock({ previousBench: SAVED_BENCH, proposedBench: shifted, lockedAthleteIds: ["D7"], roleByAthleteId: ROLE })[0]?.code,
      "bench_order_locked",
    );
  });

  it("senza bloccati dopo il buco, o senza formazione salvata, la panchina scorre come prima", () => {
    const base = { bench: cleared.benchIds, savedBench: SAVED_BENCH, lockedAthleteIds: ["D7"], roleByAthleteId: ROLE };
    assert.equal(benchAfterStarterPick({ ...base, athleteId: "C1" }), null);
    assert.equal(benchAfterStarterPick({ ...base, athleteId: "D5", savedBench: [] }), null);
    assert.equal(benchAfterStarterPick({ ...base, athleteId: "D5", lockedAthleteIds: [] }), null);
  });

  it("senza un pari ruolo da far entrare non riempie", () => {
    // P2 sale: dopo D7 ci sono solo P3 (già nella panchina salvata) e P1 bloccato.
    assert.equal(
      benchAfterStarterPick({
        bench: cleared.benchIds,
        athleteId: "P2",
        savedBench: SAVED_BENCH,
        lockedAthleteIds: ["D7", "P1"],
        roleByAthleteId: ROLE,
      }),
      null,
    );
  });

  it("svuotata a turno iniziato, si ricompone e si salva senza toccare i bloccati", () => {
    // D7 in panchina e A2 titolare hanno già giocato. Si svuota e si scelgono 11 titolari,
    // tra cui due che erano davanti a D7 in panchina.
    const locked = ["D7", "A2"];
    const start = clear(locked);
    assert.deepEqual(start.starterIds, ["", "", "", "", "", "", "", "", "", "A2", ""]);
    const starters = [...start.starterIds];
    let bench = [...start.benchIds];
    const picks: Array<[number, string]> = [
      [0, "P2"], [1, "D5"], [2, "D6"], [3, "D1"], [4, "D2"], [5, "C1"], [6, "C2"], [7, "C4"], [8, "A1"], [10, "A4"],
    ];
    for (const [slot, athleteId] of picks) {
      starters[slot] = athleteId;
      bench =
        benchAfterStarterPick({ bench, athleteId, savedBench: SAVED_BENCH, lockedAthleteIds: locked, roleByAthleteId: ROLE }) ??
        bench.filter((id) => id !== athleteId);
    }
    assert.equal(starters.filter(Boolean).length, 11);
    assert.equal(bench.indexOf("D7"), SAVED_BENCH.indexOf("D7"));
    // «Sistema la panchina», se serve, non sposta i bloccati.
    bench = restoreBenchActiveRoles(players(bench), { lockedAthleteIds: locked }).bench.map((p) => p.athleteId);
    assert.deepEqual(benchActiveShortfall(players(bench)), {});
    assert.deepEqual(
      [
        ...evaluateProgressiveLock({
          previousSlots: slotsFromLineupIds(STARTERS, SAVED_BENCH),
          proposedSlots: slotsFromLineupIds(starters, bench),
          lockedAthleteIds: locked,
        }),
        ...evaluateBenchOrderLock({ previousBench: SAVED_BENCH, proposedBench: bench, lockedAthleteIds: locked, roleByAthleteId: ROLE }),
      ],
      [],
    );
  });
});

describe("testi di «Svuota formazione»", () => {
  it("la conferma elenca bloccati, «Annulla modifiche» e la mossa", () => {
    assert.equal(CLEAR_LINEUP_CONFIRM_POINTS.length, 3);
    assert.match(CLEAR_LINEUP_CONFIRM_POINTS[1] ?? "", /«Annulla modifiche»/);
  });

  it("il messaggio dopo lo svuotamento dice chi resta in panchina solo se succede", () => {
    assert.equal(
      clearLineupSuccessMessage(0),
      "Formazione svuotata. Scegli i titolari nell'elenco «Titolari», oppure usa «Applica formazione migliore».",
    );
    assert.match(clearLineupSuccessMessage(2), /davanti a un giocatore già bloccato/);
  });
});
