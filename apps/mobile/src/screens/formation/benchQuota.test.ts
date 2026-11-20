import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
  benchQuotaSwapIds,
  benchShortfall,
  formationLineupBench,
  restoreBenchActiveRoles,
} from "./benchQuota.ts";

type Role = "P" | "D" | "C" | "A";
const players = (ids: readonly string[]) => ids.map((athleteId) => ({ athleteId, role: athleteId[0] as Role }));
const idsOf = (list: readonly { athleteId: string }[]) => list.map((player) => player.athleteId);

// Rosario, 20/11 (lega demo, Fabio Trotta): 4-4-2, l'attaccante 8° in panchina è uscito dalla
// rosa, la panchina si è ricompattata e il terzo portiere (P3, primo della tribuna) è salito al
// 10° posto. Al suo posto in rosa è arrivato A5, che non prende il voto e non è nella formazione.
const SAVED_BENCH = ["P2", "D5", "D6", "D7", "C5", "C6", "C7", "A3", "A4", "P3", "D8", "C8"];
const NEWCOMER = "A5";

describe("«Sistema la panchina» con un portiere al posto di un attaccante", () => {
  it("prima: l'attaccante appena arrivato tornava sempre in coda e il tasto non cambiava niente", () => {
    // La panchina dell'editor come la ricostruiva la schermata: chi è arrivato dopo e non può
    // essere schierato in coda, senza guardare dove era stato messo.
    const before = (placed: readonly string[]) =>
      formationLineupBench({
        orderedBench: placed,
        savedBench: SAVED_BENCH,
        placedBench: [],
        isBlocked: (id) => id === NEWCOMER,
      });
    const shown = before([...SAVED_BENCH, NEWCOMER]);
    assert.deepEqual(benchShortfall(players(shown)), { A: 1 });
    const fixed = idsOf(restoreBenchActiveRoles(players(shown)).bench);
    assert.deepEqual(before(fixed), shown);
  });

  it("ora sale l'attaccante al 10° posto e il portiere torna primo della tribuna", () => {
    const shown = formationLineupBench({
      orderedBench: [...SAVED_BENCH, NEWCOMER],
      savedBench: SAVED_BENCH,
      placedBench: SAVED_BENCH,
      isBlocked: (id) => id === NEWCOMER,
    });
    assert.deepEqual(shown, [...SAVED_BENCH, NEWCOMER]);
    const repair = restoreBenchActiveRoles(players(shown));
    const fixed = idsOf(repair.bench);
    assert.deepEqual(fixed, ["P2", "D5", "D6", "D7", "C5", "C6", "C7", "A3", "A4", NEWCOMER, "P3", "D8", "C8"]);
    assert.equal(repair.message, null);
    assert.deepEqual(repair.missing, {});
    assert.deepEqual(
      repair.moves.map(({ promoted, demoted }) => [promoted.athleteId, demoted.athleteId]),
      [[NEWCOMER, "P3"]],
    );
    // L'editor rispetta il posto scelto: l'attaccante resta nei primi 10.
    const after = formationLineupBench({
      orderedBench: fixed,
      savedBench: SAVED_BENCH,
      placedBench: fixed,
      isBlocked: (id) => id === NEWCOMER,
    });
    assert.deepEqual(after, fixed);
    assert.deepEqual(benchShortfall(players(after)), {});
  });

  it("come sul server, chi non prende il voto non alza la quota: niente da sistemare", () => {
    const bench = players([...SAVED_BENCH, NEWCOMER]);
    assert.deepEqual(benchShortfall(bench, [NEWCOMER]), {});
    const repair = restoreBenchActiveRoles(bench, [], [NEWCOMER]);
    assert.deepEqual(repair.moves, []);
    assert.equal(repair.message, null);
    assert.deepEqual(benchQuotaSwapIds(bench, 9, [NEWCOMER]), []);
  });

  it("chi non è stato messo da nessuna parte ed è bloccato resta in coda", () => {
    assert.deepEqual(
      formationLineupBench({
        orderedBench: ["A5", "P2", "D5"],
        savedBench: ["P2", "D5"],
        placedBench: ["P2", "D5"],
        isBlocked: (id) => id === "A5",
      }),
      ["P2", "D5", "A5"],
    );
  });

  it("con una partita già iniziata in mezzo non sposta nessuno e dice perché", () => {
    const bench = players([...SAVED_BENCH, NEWCOMER]);
    // D8 (11°) ha la partita iniziata: per far salire A5 bisognerebbe scavalcarlo.
    const repair = restoreBenchActiveRoles(bench, ["D8"]);
    assert.deepEqual(idsOf(repair.bench), [...SAVED_BENCH, NEWCOMER]);
    assert.deepEqual(repair.moves, []);
    assert.deepEqual(repair.missing, { A: 1 });
    assert.match(repair.message ?? "", /mancano: 1 attaccante/);
    assert.match(repair.message ?? "", /gli attaccanti in tribuna c'è chi ha la partita già iniziata/);
  });

  it("con l'unico attaccante della tribuna già in campo dice che non ce ne sono di schierabili", () => {
    const repair = restoreBenchActiveRoles(players([...SAVED_BENCH, NEWCOMER]), [NEWCOMER]);
    assert.deepEqual(repair.moves, []);
    assert.match(repair.message ?? "", /in tribuna non ci sono attaccanti schierabili: hanno la partita già iniziata/);
  });

  it("panchina in regola: niente da fare", () => {
    const bench = players(["P2", "D5", "D6", "D7", "C5", "C6", "C7", "A3", "A4", "A5", "P3"]);
    const repair = restoreBenchActiveRoles(bench);
    assert.deepEqual(idsOf(repair.bench), idsOf(bench));
    assert.deepEqual(repair.moves, []);
    assert.equal(repair.message, null);
  });
});

describe("«Cambia» con i primi 10 fuori quota", () => {
  const bench = players([...SAVED_BENCH, NEWCOMER]);

  it("sul portiere in più al 10° posto propone l'attaccante della tribuna", () => {
    assert.deepEqual(benchQuotaSwapIds(bench, 9), [NEWCOMER]);
    // Anche sul secondo portiere (è in più quanto P3).
    assert.deepEqual(benchQuotaSwapIds(bench, 0), [NEWCOMER]);
  });

  it("sull'attaccante in tribuna propone chi è in più nei primi 10", () => {
    assert.deepEqual(benchQuotaSwapIds(bench, 12), ["P2", "P3"]);
  });

  it("non propone niente su chi serve dov'è o con la panchina in regola", () => {
    assert.deepEqual(benchQuotaSwapIds(bench, 1), []);
    assert.deepEqual(benchQuotaSwapIds(bench, 10), []);
    const ok = players(["P2", "D5", "D6", "D7", "C5", "C6", "C7", "A3", "A4", "A5", "P3"]);
    assert.deepEqual(benchQuotaSwapIds(ok, 9), []);
  });
});
