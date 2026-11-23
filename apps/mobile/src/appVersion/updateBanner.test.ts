import assert from "node:assert/strict";
import { describe, it } from "node:test";
// L'app usa il confronto da `@fantappero/contracts`; il file non ha import e si carica dal sorgente.
import { isNewerAppVersion } from "../../../../packages/contracts/src/appVersion.ts";
import {
  APP_VERSION_MIN_INTERVAL_MS,
  isReturnToForeground,
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

  it("«Più tardi» nasconde quella versione finché l'app resta aperta, una più nuova lo fa tornare", () => {
    assert.equal(decide({ dismissedVersionCode: 4 }), null);
    const newer = { ...LATEST, latestVersionName: "1.4.0", latestVersionCode: 5 };
    assert.deepEqual(decide({ dismissedVersionCode: 4, latest: newer }), newer);
    // Un «Più tardi» di una versione vecchia non nasconde quella nuova.
    assert.deepEqual(decide({ dismissedVersionCode: 2 }), LATEST);
  });

  it("release 1.4: la versione si chiede a ogni ingresso, al più una volta al minuto", () => {
    const now = 1_000_000_000;
    assert.equal(APP_VERSION_MIN_INTERVAL_MS, 60_000);
    assert.equal(shouldRefreshAppVersion(null, now), true);
    assert.equal(shouldRefreshAppVersion(now - 30_000, now), false);
    assert.equal(shouldRefreshAppVersion(now - APP_VERSION_MIN_INTERVAL_MS, now), true);
    // Niente più attesa di 3 ore: dopo 5 minuti si richiede.
    assert.equal(shouldRefreshAppVersion(now - 5 * 60_000, now), true);
    // Orologio spostato indietro: si richiede di nuovo invece di aspettare.
    assert.equal(shouldRefreshAppVersion(now + 60_000, now), true);
  });

  it("release 1.4: un ritorno in primo piano è un nuovo ingresso nell'app", () => {
    assert.equal(isReturnToForeground("background", "active"), true);
    assert.equal(isReturnToForeground("inactive", "active"), true);
    // Già in primo piano, o mentre va in sfondo: niente.
    assert.equal(isReturnToForeground("active", "active"), false);
    assert.equal(isReturnToForeground("active", "background"), false);
    assert.equal(isReturnToForeground(null, "active"), false);
  });
});
