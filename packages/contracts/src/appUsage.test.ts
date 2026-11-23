import assert from "node:assert/strict";
import { describe, it } from "node:test";
import type { AdminAppUsageGroup, AdminAppUsageUser, AdminWatch } from "./admin.ts";
import { appVersionSavedMessage } from "./appVersion.ts";
import {
  appUsageGroupHint,
  appUsageGroupLabel,
  appUsageGroupTitle,
  appUsageSummaryLine,
  appUsageUserName,
  appUsageUserSeen,
  buildOperatorWatchItems,
} from "./operatorSummary.ts";

// 23/11/2026 alle 12:00 a Roma (UTC+1).
const NOW = new Date("2026-11-23T11:00:00Z");

function user(overrides: Partial<AdminAppUsageUser> = {}): AdminAppUsageUser {
  return {
    userId: "u1",
    displayName: "Bomber",
    name: null,
    email: "bomber@example.com",
    firstSeenAt: "2026-11-20T10:00:00Z",
    lastSeenAt: "2026-11-23T09:30:00Z",
    ...overrides,
  };
}

function group(overrides: Partial<AdminAppUsageGroup> = {}): AdminAppUsageGroup {
  return {
    kind: "version",
    platform: "android",
    versionName: "1.4.0",
    versionCode: 5,
    upToDate: true,
    users: [user()],
    ...overrides,
  };
}

describe("chi ha quale versione dell'app (release 1.4, Rosario 23/11)", () => {
  it("un gruppo per versione, con il conteggio", () => {
    const seven = group({ users: Array.from({ length: 7 }, (_, index) => user({ userId: `u${index}` })) });
    assert.equal(appUsageGroupTitle(seven), "1.4.0 (5): 7 utenti");
    assert.equal(appUsageGroupTitle(group()), "1.4.0 (5): 1 utente");
    assert.equal(appUsageGroupLabel(group({ versionName: null })), "versionCode 5");
    assert.equal(appUsageGroupLabel(group({ platform: "ios" })), "1.4.0 (5) · iOS");
    assert.equal(appUsageGroupHint(group()), "");
  });

  it("le app vecchie e chi non ha mai usato l'app", () => {
    const recent = group({ kind: "unknown_recent", versionName: null, versionCode: null, upToDate: false });
    const old = group({ kind: "unknown", versionName: null, versionCode: null, upToDate: false });
    const never = group({ kind: "never", platform: null, versionName: null, versionCode: null, upToDate: false, users: [] });
    assert.equal(appUsageGroupTitle(recent), "Versione non nota (app 1.2 o 1.3): 1 utente");
    assert.equal(appUsageGroupTitle(old), "Versione non nota (app 1.1 o precedente): 1 utente");
    assert.equal(appUsageGroupTitle(never), "App mai usata / solo sito: 0 utenti");
    assert.match(appUsageGroupHint(recent), /dalla 1\.4/);
    assert.notEqual(appUsageGroupHint(old), "");
    assert.notEqual(appUsageGroupHint(never), "");
  });

  it("nome, email a parte, e ultima volta nell'app in ora italiana", () => {
    assert.equal(appUsageUserName(user()), "Bomber");
    assert.equal(appUsageUserName(user({ name: "Mario Rossi" })), "Bomber (Mario Rossi)");
    assert.equal(appUsageUserSeen(user(), NOW), "visto nell'app oggi alle 10:30");
    assert.equal(appUsageUserSeen(user({ lastSeenAt: "2026-11-22T20:00:00Z" }), NOW), "visto nell'app ieri alle 21:00");
    assert.equal(appUsageUserSeen(user({ lastSeenAt: null }), NOW), "");
  });

  it("riga del Riepilogo: aggiornati su chi usa l'app", () => {
    assert.equal(appUsageSummaryLine({ upToDateUsers: 4, appUsers: 12 }), "4 utenti aggiornati su 12 che usano l'app");
    assert.equal(appUsageSummaryLine({ upToDateUsers: 1, appUsers: 1 }), "1 utente aggiornato su 1 che usa l'app");
    const base: AdminWatch = {
      generatedAt: NOW.toISOString(),
      testerRequestsPending: 0,
      oldestTesterRequestAt: null,
      feedbackNew: 0,
      latestFeedbackAt: null,
      jobsDisabled: [],
      jobFailuresSince: NOW.toISOString(),
      jobFailures: [],
      listoneLastUpdate: null,
      currentRounds: { activeLeagues: 0, leaguesInProgress: 0, roundNumbers: [] },
      nextLineupLock: null,
      androidAppVersion: {
        latestVersionName: "1.3.0",
        latestVersionCode: 4,
        downloadUrl: "https://example.com/app.apk",
        message: null,
      },
    };
    const withUsage = buildOperatorWatchItems({ ...base, androidAppUsage: { upToDateUsers: 4, appUsers: 12 } }, NOW)[5];
    assert.equal(withUsage?.title, "App Android annunciata: 1.3.0");
    assert.deepEqual(withUsage?.details, ["4 utenti aggiornati su 12 che usano l'app"]);
    // Server più vecchio (nessun conteggio): la riga di prima.
    const older = buildOperatorWatchItems(base, NOW)[5];
    assert.deepEqual(older?.details, ["Chi ha una versione più vecchia vede l'avviso"]);
  });

  it("messaggio dopo il salvataggio: quante notifiche sono partite", () => {
    const android = { latestVersionName: "1.4.0", latestVersionCode: 5, downloadUrl: "https://x.example/a", message: null };
    assert.equal(
      appVersionSavedMessage({ android, notifiedUsers: 7 }),
      "Versione salvata: notifica inviata a 7 utenti che non hanno ancora questa versione.",
    );
    assert.equal(
      appVersionSavedMessage({ android, notifiedUsers: 1 }),
      "Versione salvata: notifica inviata a 1 utente che non ha ancora questa versione.",
    );
    assert.match(appVersionSavedMessage({ android, notifiedUsers: 0 }), /Nessuna notifica nuova/);
    assert.match(appVersionSavedMessage({ android, notifiedUsers: null }), /non è partita/);
    // Server più vecchio: il testo di prima.
    assert.equal(appVersionSavedMessage({ android }), "Versione salvata: chi ha un'app più vecchia vedrà l'avviso.");
  });
});
