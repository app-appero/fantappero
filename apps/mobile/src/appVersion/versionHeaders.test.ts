import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { appVersionHeaders } from "./versionHeaders.ts";

describe("versione dell'app in ogni richiesta (release 1.4, Rosario 23/11)", () => {
  it("sull'APK Android manda nome, versionCode e piattaforma", () => {
    assert.deepEqual(appVersionHeaders("android", "1.4.0", 5), {
      "X-App-Version": "1.4.0",
      "X-App-Version-Code": "5",
      "X-App-Platform": "android",
    });
    assert.equal(appVersionHeaders("android", " 1.4.0 ", 5)["X-App-Version"], "1.4.0");
  });

  it("senza un nome leggibile manda solo il versionCode", () => {
    assert.deepEqual(appVersionHeaders("android", undefined, 5), {
      "X-App-Version-Code": "5",
      "X-App-Platform": "android",
    });
    assert.equal(appVersionHeaders("android", "1.4 beta", 5)["X-App-Version"], undefined);
  });

  it("niente intestazioni senza versionCode, sul web o su iOS", () => {
    assert.deepEqual(appVersionHeaders("android", "1.4.0", null), {});
    assert.deepEqual(appVersionHeaders("android", "1.4.0", 0), {});
    assert.deepEqual(appVersionHeaders("android", "1.4.0", 2.5), {});
    assert.deepEqual(appVersionHeaders("web", "1.4.0", 5), {});
    assert.deepEqual(appVersionHeaders("ios", "1.4.0", 5), {});
  });
});
