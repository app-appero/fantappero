import assert from "node:assert/strict";
import { describe, it } from "node:test";
import type { SystemJob } from "./admin.ts";
import { COACH_TYPE_OPTIONS, NO_COACH_FILTERS, hasCoachFilters } from "./coachDirectoryFilters.ts";
import { formatTimeUntil, jobsSummaryTiles, nextJobToRun } from "./jobsSummary.ts";
import {
  CUSTOM_RAISE_LABEL,
  customRaiseAmount,
  customRaisePlaceholder,
  raiseButtonLabel,
  raiseTargetAmount,
} from "./liveRaise.ts";

const NOW = Date.parse("2026-11-28T10:00:00.000Z");

function job(key: string, enabled: boolean, nextInMinutes: number | null): SystemJob {
  return {
    key,
    title: `Job ${key}`,
    description: "",
    task: key,
    enabled,
    intervalSeconds: 3600,
    minIntervalSeconds: 60,
    maxIntervalSeconds: 86400,
    lastStartedAt: null,
    nextRunAt: nextInMinutes === null ? null : new Date(NOW + nextInMinutes * 60000).toISOString(),
    usesProviderQuota: false,
    sendsNotifications: false,
    running: false,
    lastRun: null,
  };
}

describe("riepilogo dei Job automatici (sito e app 1.5)", () => {
  it("quanto manca alla prossima partenza", () => {
    assert.equal(formatTimeUntil(null, NOW), "—");
    assert.equal(formatTimeUntil(new Date(NOW - 5000).toISOString(), NOW), "ora");
    assert.equal(formatTimeUntil(new Date(NOW + 12 * 60000).toISOString(), NOW), "12 min");
    assert.equal(formatTimeUntil(new Date(NOW + 3 * 3600000).toISOString(), NOW), "3 h");
    assert.equal(formatTimeUntil(new Date(NOW + 2 * 86400000).toISOString(), NOW), "2 g");
  });

  it("«Attivi» e «Prossimo giro»", () => {
    const jobs = [job("a", true, 90), job("b", false, 5), job("c", true, 12)];
    assert.equal(nextJobToRun(jobs)?.key, "c");
    assert.deepEqual(jobsSummaryTiles(jobs, NOW), [
      { label: "Attivi", value: "2 / 3", hint: "1 spento" },
      { label: "Prossimo giro", value: "12 min", hint: "Job c" },
    ]);
  });

  it("con tutti i job spenti non c'è un prossimo giro; senza job nessun riquadro", () => {
    const tiles = jobsSummaryTiles([job("a", false, 5), job("b", false, null)], NOW);
    assert.deepEqual(tiles, [
      { label: "Attivi", value: "0 / 2", hint: "2 spenti" },
      { label: "Prossimo giro", value: "—", hint: "Nessun job attivo" },
    ]);
    assert.deepEqual(jobsSummaryTiles([], NOW), []);
  });
});

describe("filtri della directory fantallenatori (sito e app 1.5)", () => {
  it("la tipologia ha Tutte, Manuale e IA", () => {
    assert.deepEqual(
      COACH_TYPE_OPTIONS.map((option) => [option.value, option.label]),
      [
        ["", "Tutte"],
        ["human", "Manuale"],
        ["ai", "IA"],
      ],
    );
  });

  it("«Reimposta filtri» compare solo con un filtro attivo", () => {
    assert.equal(hasCoachFilters(NO_COACH_FILTERS), false);
    assert.equal(hasCoachFilters({ ...NO_COACH_FILTERS, query: "mar" }), true);
    assert.equal(hasCoachFilters({ ...NO_COACH_FILTERS, userType: "ai" }), true);
    assert.equal(hasCoachFilters({ ...NO_COACH_FILTERS, onlyAvailable: true }), true);
  });
});

describe("asta live: «Offerta personalizzata» (sito e app 1.5)", () => {
  it("l'importo scritto vale se è un numero positivo", () => {
    assert.equal(CUSTOM_RAISE_LABEL, "Offerta personalizzata");
    assert.equal(customRaiseAmount("25"), 25);
    assert.equal(customRaiseAmount(" 7 "), 7);
    assert.equal(customRaiseAmount(""), null);
    assert.equal(customRaiseAmount("0"), null);
    assert.equal(customRaiseAmount("-3"), null);
    assert.equal(customRaiseAmount("abc"), null);
  });

  it("il pulsante rilancia l'offerta personalizzata, altrimenti il minimo", () => {
    assert.equal(raiseTargetAmount("25", 11), 25);
    assert.equal(raiseTargetAmount("", 11), 11);
    assert.equal(raiseTargetAmount("0", 11), 11);
    assert.equal(raiseTargetAmount("", null), null);
    assert.equal(raiseButtonLabel("25", 11), "Rilancia a 25");
    assert.equal(raiseButtonLabel("", 11), "Rilancia a 11");
    assert.equal(raiseButtonLabel("", null), "Rilancia a —");
    assert.equal(customRaisePlaceholder(11), "Es. 16");
    assert.equal(customRaisePlaceholder(null), "");
  });
});
