import assert from "node:assert/strict";
import { describe, it } from "node:test";
import type { AthleteCareerRow } from "@fantappero/contracts";
import {
  careerRowModels,
  careerSeasonTitle,
  careerStatLabels,
  currentSeasonSummary,
  isGoalkeeperRole,
  sortCareerRows,
} from "./athleteCareer.ts";

function row(overrides: Partial<AthleteCareerRow>): AthleteCareerRow {
  return {
    seasonYear: 2025,
    seasonLabel: "25/26",
    isCurrent: false,
    source: "provider",
    clubId: null,
    clubName: "Lazio",
    competitionId: null,
    competitionName: "Serie A",
    appearances: 30,
    minutes: 2500,
    averageRating: 6.7,
    votes: null,
    fantasyAverage: null,
    goals: 14,
    assists: 5,
    goalsConceded: null,
    saves: null,
    penaltiesSaved: null,
    yellowCards: 3,
    redCards: 0,
    cleanSheets: null,
    ...overrides,
  };
}

// Portiere dell'esempio del canvas («Esempio portiere»).
const goalkeeperCareer: AthleteCareerRow[] = [
  row({ seasonYear: 2024, seasonLabel: "24/25", appearances: 31, goalsConceded: 34, penaltiesSaved: 2, saves: 90, averageRating: 6.35, goals: 0, assists: 0 }),
  row({
    seasonYear: 2025,
    clubName: "Bournemouth",
    competitionName: "Premier League",
    appearances: 28,
    goalsConceded: 39,
    penaltiesSaved: 0,
    saves: 80,
    averageRating: 6.18,
  }),
  row({
    seasonYear: 2026,
    seasonLabel: "26/27",
    isCurrent: true,
    source: "fantappero",
    appearances: 12,
    votes: 12,
    goalsConceded: 11,
    cleanSheets: 5,
    penaltiesSaved: 1,
    saves: 30,
    averageRating: 6.4,
    fantasyAverage: 6.9,
    goals: 0,
    assists: 0,
  }),
];

describe("carriera della scheda calciatore", () => {
  it("dalla stagione più recente, compresa quella in corso", () => {
    assert.deepEqual(
      sortCareerRows(goalkeeperCareer).map((entry) => entry.seasonYear),
      [2026, 2025, 2024],
    );
    const models = careerRowModels(goalkeeperCareer, { goalkeeper: true });
    assert.equal(models[0]?.title, "2026/27 · Lazio");
    assert.equal(models[0]?.isCurrent, true);
    assert.equal(models[1]?.title, "2025/26 · Bournemouth");
    assert.equal(models[1]?.competition, "Premier League");
    assert.equal(careerSeasonTitle(2024), "2024/25");
    assert.equal(careerSeasonTitle(2099), "2099/00");
  });

  it("portiere: gol subiti, porte inviolate (solo stagione in corso), rigori parati, parate e media", () => {
    assert.equal(isGoalkeeperRole("P"), true);
    assert.equal(isGoalkeeperRole("A"), false);
    assert.equal(isGoalkeeperRole(null), false);
    assert.deepEqual(careerStatLabels(true), [
      "Presenze",
      "Gol subiti",
      "Porte inviolate",
      "Rigori parati",
      "Parate",
      "Media voto",
    ]);
    const [currentSeason, lastSeason] = careerRowModels(goalkeeperCareer, { goalkeeper: true });
    assert.deepEqual(
      currentSeason?.stats.map((stat) => [stat.short, stat.value]),
      [
        ["pres.", "12"],
        ["subiti", "11"],
        ["inviolate", "5"],
        ["rig. parati", "1"],
        ["parate", "30"],
        ["media", "6,40"],
      ],
    );
    // Stagione passata: porte inviolate non note → «—».
    assert.equal(lastSeason?.stats.find((stat) => stat.key === "cleanSheets")?.value, "—");
    assert.equal(lastSeason?.stats.find((stat) => stat.key === "goalsConceded")?.value, "39");
  });

  it("calciatore di movimento: presenze, gol, assist e media voto", () => {
    const [model] = careerRowModels([row({ averageRating: null })], { goalkeeper: false });
    assert.deepEqual(
      model?.stats.map((stat) => [stat.label, stat.value]),
      [
        ["Presenze", "30"],
        ["Gol", "14"],
        ["Assist", "5"],
        ["Media voto", "—"],
      ],
    );
    assert.match(model?.accessibilityLabel ?? "", /^2025\/26, Lazio, Serie A: Presenze 30, Gol 14/);
  });

  it("squadra o campionato mancanti", () => {
    const [model] = careerRowModels([row({ clubName: null, competitionName: null })], { goalkeeper: false });
    assert.equal(model?.title, "2025/26 · Squadra non nota");
    assert.equal(model?.competition, null);
    assert.deepEqual(careerRowModels(undefined, { goalkeeper: false }), []);
  });

  it("caselle della stagione in corso del portiere", () => {
    const summary = currentSeasonSummary(goalkeeperCareer, { goalkeeper: true });
    assert.equal(summary?.title, "Stagione 2026/27 · in corso");
    assert.deepEqual(
      summary?.tiles.map((tile) => [tile.label, tile.value]),
      [
        ["Presenze", "12"],
        ["Gol subiti", "11"],
        ["Porte inviolate", "5"],
        ["Rigori parati", "1"],
        ["Parate", "30"],
        ["Media voto", "6,40"],
        ["Fantamedia", "6,90"],
      ],
    );
  });

  it("stagione in corso con cambio di squadra: somme e media pesata", () => {
    const summary = currentSeasonSummary(
      [
        row({ seasonYear: 2026, isCurrent: true, clubName: "Genoa", appearances: 4, votes: 4, goals: 1, assists: 0, averageRating: 6, redCards: 1 }),
        row({ seasonYear: 2026, isCurrent: true, clubName: "Lazio", appearances: 12, votes: 12, goals: 5, assists: 2, averageRating: 7, redCards: 0 }),
      ],
      { goalkeeper: false },
    );
    assert.deepEqual(
      summary?.tiles.map((tile) => [tile.label, tile.value]),
      [
        ["Presenze", "16"],
        ["Gol", "6"],
        ["Assist", "2"],
        ["Media voto", "6,75"],
        ["Fantamedia", "—"],
        ["Espulsioni", "1"],
      ],
    );
  });

  it("senza stagione in corso nessuna casella", () => {
    assert.equal(currentSeasonSummary([row({})], { goalkeeper: false }), null);
    assert.equal(currentSeasonSummary(undefined, { goalkeeper: false }), null);
  });
});
