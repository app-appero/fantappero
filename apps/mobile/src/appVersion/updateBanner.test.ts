import assert from "node:assert/strict";
import { describe, it } from "node:test";
// L'app usa il confronto da `@fantappero/contracts`; il file non ha import e si carica dal sorgente.
import { isNewerAppVersion } from "../../../../packages/contracts/src/appVersion.ts";
import {
  APP_VERSION_REFRESH_MS,
  parseDismissedVersionCode,
  shouldRefreshAppVersion,
  updateBannerVersion,
  type UpdateBannerInput,
} from "./updateBanner.ts";

const LATEST = {
  latestVersionName: "1.3.0",
  latestVersionCode: 4,
  downloadUrl: "https://drive.google.com/drive/folders/prova",
  message: null,
};

const BASE: UpdateBannerInput = {
  platformOS: "android",
  signedIn: true,
  installedVersionCode: 3,
  latest: LATEST,
  dismissedVersionCode: null,
};

function decide(overrides: Partial<UpdateBannerInput> = {}) {
  return updateBannerVersion({ ...BASE, ...overrides }, isNewerAppVersion);
}

describe("avviso nuova versione dell'app (pilota-1.2, Rosario 21/11)", () => {
  it("si mostra quando il server ha una versione più nuova di quella installata", () => {
    assert.deepEqual(decide(), LATEST);
  });

  it("non si mostra con la stessa versione, una più vecchia o senza configurazione", () => {
    assert.equal(decide({ installedVersionCode: 4 }), null);
    assert.equal(decide({ installedVersionCode: 5 }), null);
    assert.equal(decide({ latest: null }), null);
    assert.equal(decide({ installedVersionCode: null }), null);
  });

  it("non si mostra senza accesso (accesso, registrazione, richiesta tester)", () => {
    assert.equal(decide({ signedIn: false }), null);
  });

  it("solo sull'app Android, non sul sito", () => {
    assert.equal(decide({ platformOS: "web" }), null);
    assert.equal(decide({ platformOS: "ios" }), null);
  });

  it("«Più tardi» nasconde quella versione, una più nuova lo fa tornare", () => {
    assert.equal(decide({ dismissedVersionCode: 4 }), null);
    const newer = { ...LATEST, latestVersionName: "1.4.0", latestVersionCode: 5 };
    assert.deepEqual(decide({ dismissedVersionCode: 4, latest: newer }), newer);
    // Un «Più tardi» di una versione vecchia non nasconde quella nuova.
    assert.deepEqual(decide({ dismissedVersionCode: 2 }), LATEST);
  });

  it("la versione si richiede al più ogni 3 ore", () => {
    const now = 1_000_000_000;
    assert.equal(shouldRefreshAppVersion(null, now), true);
    assert.equal(shouldRefreshAppVersion(now - 60_000, now), false);
    assert.equal(shouldRefreshAppVersion(now - APP_VERSION_REFRESH_MS, now), true);
    // Orologio spostato indietro: si richiede di nuovo invece di aspettare.
    assert.equal(shouldRefreshAppVersion(now + 60_000, now), true);
  });

  it("il «Più tardi» salvato si rilegge; un valore rovinato vale «mai»", () => {
    assert.equal(parseDismissedVersionCode("4"), 4);
    assert.equal(parseDismissedVersionCode(null), null);
    assert.equal(parseDismissedVersionCode(""), null);
    assert.equal(parseDismissedVersionCode("abc"), null);
    assert.equal(parseDismissedVersionCode("0"), null);
    assert.equal(parseDismissedVersionCode("-2"), null);
  });
});
