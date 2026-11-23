import assert from "node:assert/strict";
import { describe, it } from "node:test";
import type { AdminWatch } from "./admin.ts";
import {
  buildOperatorWatchItems,
  formatLeaguesByState,
  formatRomeDayMonth,
  formatRomeDaysAgo,
  formatRomeWhen,
  listoneUpdateSummary,
} from "./operatorSummary.ts";

// 22/11/2026 alle 10:00 a Roma (UTC+1).
const NOW = new Date("2026-11-22T09:00:00Z");

function watch(overrides: Partial<AdminWatch> = {}): AdminWatch {
  return {
    generatedAt: NOW.toISOString(),
    testerRequestsPending: 0,
    oldestTesterRequestAt: null,
    feedbackNew: 0,
    latestFeedbackAt: null,
    jobsDisabled: [],
    jobFailuresSince: "2026-11-21T09:00:00Z",
    jobFailures: [],
    listoneLastUpdate: null,
    currentRounds: { activeLeagues: 0, leaguesInProgress: 0, roundNumbers: [] },
    nextLineupLock: null,
    androidAppVersion: null,
    ...overrides,
  };
}

describe("Riepilogo operatore: date in ora italiana", () => {
  it("dice oggi, ieri e domani secondo il calendario di Roma", () => {
    assert.equal(formatRomeWhen("2026-11-22T14:00:00Z", NOW), "oggi alle 15:00");
    assert.equal(formatRomeWhen("2026-11-21T20:40:00Z", NOW), "ieri alle 21:40");
    assert.equal(formatRomeWhen("2026-11-23T08:05:00Z", NOW), "domani alle 9:05");
    assert.equal(formatRomeWhen("2026-11-19T14:00:00Z", NOW), "19/11 alle 15:00");
    // 23:30 UTC del 21/11 è già il 22/11 a Roma.
    assert.equal(formatRomeWhen("2026-11-21T23:30:00Z", NOW), "oggi alle 0:30");
    assert.equal(formatRomeWhen(null, NOW), "—");
  });

  it("conta i giorni passati", () => {
    assert.equal(formatRomeDaysAgo("2026-11-22T06:00:00Z", NOW), "oggi");
    assert.equal(formatRomeDaysAgo("2026-11-21T06:00:00Z", NOW), "ieri");
    assert.equal(formatRomeDaysAgo("2026-11-19T06:00:00Z", NOW), "3 giorni fa");
    assert.equal(formatRomeDayMonth("2026-11-19T06:00:00Z"), "19/11");
  });
});

describe("Riepilogo operatore: leghe per stato", () => {
  it("raggruppa come nel canvas", () => {
    assert.equal(
      formatLeaguesByState({ active: 2, auction: 1, draft: 1 }),
      "2 in corso · 1 all'asta · 1 in preparazione",
    );
    assert.equal(
      formatLeaguesByState({ configuring: 1, draft: 2, concluded: 1, archived: 2 }),
      "3 in preparazione · 1 conclusa · 2 archiviate",
    );
    assert.equal(formatLeaguesByState({}), "");
    assert.equal(formatLeaguesByState(undefined), "");
  });
});

describe("Riepilogo operatore: «Da guardare»", () => {
  it("con niente da fare ha sei righe tranquille, ognuna col suo link", () => {
    const items = buildOperatorWatchItems(watch(), NOW);
    assert.deepEqual(
      items.map((row) => [row.id, row.tone, row.targetLabel]),
      [
        ["testers", "ok", "Utenti"],
        ["feedback", "ok", "Segnalazioni"],
        ["jobs", "ok", "Job automatici"],
        ["listone", "idle", "Listone"],
        ["rounds", "idle", "Turni"],
        ["app-version", "idle", "Versione app"],
      ],
    );
    assert.equal(items[2]?.title, "Tutti i job sono accesi");
    assert.deepEqual(items[2]?.details, ["Nessun errore nelle ultime 24 ore"]);
  });

  it("richieste tester e segnalazioni in attesa sono da guardare", () => {
    const [testers, feedback] = buildOperatorWatchItems(
      watch({
        testerRequestsPending: 3,
        oldestTesterRequestAt: "2026-11-20T08:00:00Z",
        feedbackNew: 2,
        latestFeedbackAt: "2026-11-21T20:40:00Z",
      }),
      NOW,
    );
    assert.equal(testers?.tone, "warn");
    assert.equal(testers?.title, "3 richieste tester in attesa");
    assert.deepEqual(testers?.details, ["La più vecchia è di 2 giorni fa"]);
    assert.equal(feedback?.title, "2 segnalazioni nuove");
    assert.deepEqual(feedback?.details, ["L'ultima ieri alle 21:40"]);

    const [oneTester, oneReport] = buildOperatorWatchItems(
      watch({
        testerRequestsPending: 1,
        oldestTesterRequestAt: "2026-11-22T08:12:00Z",
        feedbackNew: 1,
        latestFeedbackAt: "2026-11-22T07:00:00Z",
      }),
      NOW,
    );
    assert.equal(oneTester?.title, "1 richiesta tester in attesa");
    assert.deepEqual(oneTester?.details, ["Arrivata oggi alle 9:12"]);
    assert.equal(oneReport?.title, "1 segnalazione nuova");
  });

  it("job spenti e giri finiti con errore, con il motivo", () => {
    const jobs = buildOperatorWatchItems(
      watch({
        jobsDisabled: [{ key: "fantasy-lineups-generate-ai", title: "Formazioni IA" }],
        jobFailures: [
          {
            jobKey: "sports-poll-late",
            title: "Correzioni tardive",
            failedAt: "2026-11-22T02:12:00Z",
            reason: "Fornitore sportivo: troppe richieste, limite raggiunto (ProviderRateLimitError).",
            failures: 2,
            lastOutcome: "failed",
            lastFinishedAt: "2026-11-22T02:12:00Z",
          },
        ],
      }),
      NOW,
    )[2];
    assert.equal(jobs?.tone, "bad");
    assert.equal(jobs?.title, "1 job spento: Formazioni IA");
    assert.deepEqual(jobs?.details, [
      "Errore in «Correzioni tardive» oggi alle 3:12 (2 volte): Fornitore sportivo: troppe richieste, limite raggiunto (ProviderRateLimitError).",
    ]);
  });

  it("un job già ripartito resta da guardare ma non è rosso", () => {
    const jobs = buildOperatorWatchItems(
      watch({
        jobFailures: [
          {
            jobKey: "market-values-refresh",
            title: "Medie e Valore di mercato",
            failedAt: "2026-11-21T22:00:00Z",
            reason: null,
            failures: 1,
            lastOutcome: "ok",
            lastFinishedAt: "2026-11-22T08:00:00Z",
          },
        ],
      }),
      NOW,
    )[2];
    assert.equal(jobs?.tone, "warn");
    assert.equal(jobs?.title, "1 job con errori nelle ultime 24 ore");
    assert.match(jobs?.details[0] ?? "", /motivo non registrato\. Poi è ripartito bene\.$/);
  });

  it("ultimo aggiornamento del listone con data, autore e riassunto", () => {
    const update = {
      updatedAt: "2026-11-19T15:30:00Z",
      seasonYear: 2026,
      kind: "refresh" as const,
      source: "operator" as const,
      authorDisplayName: "Rosario",
      leagueName: null,
      added: 3,
      removed: 1,
      changed: 12,
    };
    const listone = buildOperatorWatchItems(watch({ listoneLastUpdate: update }), NOW)[3];
    assert.equal(listone?.tone, "ok");
    assert.equal(listone?.title, "Listone aggiornato il 19/11");
    assert.deepEqual(listone?.details, ["3 giorni fa · da Rosario", "3 nuovi, 1 tolto, 12 cambiati"]);
    assert.equal(
      listoneUpdateSummary({ ...update, kind: "roles_from_provider", changed: 1 }),
      "Ruoli presi dal fornitore: 1 calciatore",
    );
    const fromLeague = buildOperatorWatchItems(
      watch({ listoneLastUpdate: { ...update, source: "league", leagueName: "Lega del Lunedì" } }),
      NOW,
    )[3];
    assert.equal(fromLeague?.details[0], "3 giorni fa · da Rosario (lega Lega del Lunedì)");
  });

  it("giornata in corso e prossimo blocco fra tutte le leghe", () => {
    const rounds = buildOperatorWatchItems(
      watch({
        currentRounds: { activeLeagues: 4, leaguesInProgress: 3, roundNumbers: [12] },
        nextLineupLock: {
          lockAt: "2026-11-22T14:00:00Z",
          leagueId: "l1",
          leagueName: "Lega del Lunedì",
          roundNumber: 12,
        },
      }),
      NOW,
    )[4];
    assert.equal(rounds?.title, "Giornata 12 in corso in 3 leghe su 4");
    assert.deepEqual(rounds?.details, [
      "Prossimo blocco formazioni: oggi alle 15:00 (Lega del Lunedì, giornata 12)",
    ]);
    const mixed = buildOperatorWatchItems(
      watch({ currentRounds: { activeLeagues: 2, leaguesInProgress: 1, roundNumbers: [11, 12] } }),
      NOW,
    )[4];
    assert.equal(mixed?.title, "Giornate 11–12 in corso in 1 lega su 2");
    assert.deepEqual(mixed?.details, ["Nessun blocco formazioni in arrivo"]);
  });

  it("versione dell'app annunciata", () => {
    const app = buildOperatorWatchItems(
      watch({
        androidAppVersion: {
          latestVersionName: "1.3.0",
          latestVersionCode: 4,
          downloadUrl: "https://example.com/app.apk",
          message: null,
        },
      }),
      NOW,
    )[5];
    assert.equal(app?.tone, "ok");
    assert.equal(app?.title, "App Android annunciata: 1.3.0");
    assert.equal(app?.target, "admin-app-version");
  });
});
