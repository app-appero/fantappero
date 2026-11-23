import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
  EMPTY_APP_VERSION_FORM,
  appUpdateBannerText,
  appVersionFormFrom,
  appVersionUpdateFrom,
  displayAppVersionName,
  isHttpsDownloadUrl,
  isNewerAppVersion,
  validateAppVersionForm,
} from "./appVersion.ts";

describe("versione dell'app Android (pilota-1.2, Rosario 21/11)", () => {
  it("c'è una versione più nuova solo se il versionCode pubblicato è più alto", () => {
    assert.equal(isNewerAppVersion(3, 4), true);
    assert.equal(isNewerAppVersion(3, 3), false);
    assert.equal(isNewerAppVersion(4, 3), false);
    // 1 = pilota-1 e 1.1 (versionCode mai cambiato), 3 = 1.2.
    assert.equal(isNewerAppVersion(1, 3), true);
  });

  it("senza numeri validi non si confronta: nessun avviso", () => {
    assert.equal(isNewerAppVersion(null, 4), false);
    assert.equal(isNewerAppVersion(undefined, 4), false);
    assert.equal(isNewerAppVersion(3, null), false);
    assert.equal(isNewerAppVersion(3, 0), false);
    assert.equal(isNewerAppVersion(0, 4), false);
    assert.equal(isNewerAppVersion(3, 4.5), false);
    assert.equal(isNewerAppVersion(3, Number.NaN), false);
  });

  it("il nome si mostra senza lo zero finale", () => {
    assert.equal(displayAppVersionName("1.3.0"), "1.3");
    assert.equal(displayAppVersionName("2.0.0"), "2.0");
    assert.equal(displayAppVersionName("1.3.1"), "1.3.1");
    assert.equal(displayAppVersionName(" 1.4 "), "1.4");
    assert.equal(appUpdateBannerText("1.3.0"), "È disponibile la versione 1.3 dell'app.");
  });

  it("il link di download è solo https", () => {
    assert.equal(isHttpsDownloadUrl("https://drive.google.com/drive/folders/abc"), true);
    assert.equal(isHttpsDownloadUrl(" https://example.com/app.apk "), true);
    assert.equal(isHttpsDownloadUrl("https://example.com:8443"), true);
    assert.equal(isHttpsDownloadUrl("http://example.com/app.apk"), false);
    assert.equal(isHttpsDownloadUrl("javascript:alert(1)"), false);
    assert.equal(isHttpsDownloadUrl("https://"), false);
    assert.equal(isHttpsDownloadUrl("https://example.com/a b"), false);
    assert.equal(isHttpsDownloadUrl("example.com/app.apk"), false);
  });
});

describe("modulo «Versione app» del pannello operatore (sito e app, 1.4)", () => {
  it("precompila i campi con la versione annunciata", () => {
    assert.deepEqual(appVersionFormFrom({ android: null }), EMPTY_APP_VERSION_FORM);
    assert.deepEqual(
      appVersionFormFrom({
        android: {
          latestVersionName: "1.3.0",
          latestVersionCode: 4,
          downloadUrl: "https://example.com/app.apk",
          message: null,
        },
      }),
      { name: "1.3.0", code: "4", url: "https://example.com/app.apk", message: "" },
    );
  });

  it("controlla i campi con gli stessi testi del sito", () => {
    assert.deepEqual(
      validateAppVersionForm({
        name: "1.3.0",
        code: "4",
        url: "https://example.com/a.apk",
        message: "",
      }),
      {},
    );
    const errors = validateAppVersionForm({
      name: "uno",
      code: "0",
      url: "http://example.com",
      message: "x".repeat(201),
    });
    assert.equal(errors.name, "Scrivi la versione con numeri e punti, per esempio 1.3.0.");
    assert.equal(errors.code, "Il versionCode è un numero intero maggiore di zero.");
    assert.equal(errors.url, "Il link deve iniziare con https://");
    assert.equal(errors.message, "Il messaggio può avere al massimo 200 caratteri.");
    assert.ok(validateAppVersionForm({ ...EMPTY_APP_VERSION_FORM, code: "4.5" }).code);
  });

  it("prepara il corpo della richiesta", () => {
    assert.deepEqual(
      appVersionUpdateFrom({
        name: " 1.4.0 ",
        code: " 5 ",
        url: " https://e.com/a.apk ",
        message: "  ",
      }),
      {
        latestVersionName: "1.4.0",
        latestVersionCode: 5,
        downloadUrl: "https://e.com/a.apk",
        message: null,
      },
    );
  });
});
