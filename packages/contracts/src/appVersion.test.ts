import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
  appUpdateBannerText,
  displayAppVersionName,
  isHttpsDownloadUrl,
  isNewerAppVersion,
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
