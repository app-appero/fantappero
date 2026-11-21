import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { appVersionLabel } from "./versionLabel.ts";

describe("versione dell'app nelle segnalazioni (pilota-1.2, Rosario 21/11)", () => {
  it("versionName e versionCode di app.json: «1.2.0 (3)»", () => {
    assert.equal(appVersionLabel("1.2.0", 3), "1.2.0 (3)");
    assert.equal(appVersionLabel(" 1.2.0 ", 3), "1.2.0 (3)");
  });

  it("con un solo dato manda quello che c'è", () => {
    assert.equal(appVersionLabel("1.2.0", null), "1.2.0");
    assert.equal(appVersionLabel("1.2.0", undefined), "1.2.0");
    assert.equal(appVersionLabel(undefined, 3), "(3)");
  });

  it("senza dati leggibili non manda nulla", () => {
    assert.equal(appVersionLabel(undefined, undefined), undefined);
    assert.equal(appVersionLabel("  ", 0), undefined);
    assert.equal(appVersionLabel(null, 2.5), undefined);
  });

  it("sta nel campo del backend (32 caratteri)", () => {
    assert.ok((appVersionLabel("1.2.0", 3) ?? "").length <= 32);
  });
});
