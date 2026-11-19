import assert from "node:assert/strict";
import test from "node:test";
import { auctionModeFromParams } from "./auctionMode.ts";

test("la modalità richiesta dai parametri di navigazione apre la scheda giusta", () => {
  assert.equal(auctionModeFromParams({ modalita: "live" }), "live");
  assert.equal(auctionModeFromParams({ modalita: "buste" }), "buste");
});

test("parametri assenti o sconosciuti non impongono una scheda", () => {
  for (const params of [undefined, null, {}, { modalita: "" }, { modalita: "rilanci" }, { modalita: 3 }, { stato: "vuoto" }]) {
    assert.equal(auctionModeFromParams(params), undefined, JSON.stringify(params));
  }
});
