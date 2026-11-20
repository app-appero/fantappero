import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { ownershipSourceLabel } from "./ownershipSource.ts";

describe("ownershipSourceLabel (storico della rosa, QA 19-20/11)", () => {
  it("traduce ogni origine del possesso inviata dal backend", () => {
    assert.equal(ownershipSourceLabel("manual"), "Inserimento manuale");
    assert.equal(ownershipSourceLabel("csv_import"), "Importazione da file");
    assert.equal(ownershipSourceLabel("admin"), "Assegnazione admin");
    assert.equal(ownershipSourceLabel("market"), "Mercato");
  });

  it("un'origine sconosciuta ha un'etichetta generica, mai il codice", () => {
    assert.equal(ownershipSourceLabel("origine_futura"), "Altro");
    assert.equal(ownershipSourceLabel(""), "Altro");
    assert.equal(ownershipSourceLabel("toString"), "Altro");
  });
});
