import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { auctionHubHasLeague, auctionModeFromParams } from "./auctionMode.ts";

test("la modalità richiesta dai parametri di navigazione apre la scheda giusta", () => {
  assert.equal(auctionModeFromParams({ modalita: "live" }), "live");
  assert.equal(auctionModeFromParams({ modalita: "buste" }), "buste");
});

test("parametri assenti o sconosciuti non impongono una scheda", () => {
  for (const params of [undefined, null, {}, { modalita: "" }, { modalita: "rilanci" }, { modalita: 3 }, { stato: "vuoto" }]) {
    assert.equal(auctionModeFromParams(params), undefined, JSON.stringify(params));
  }
});

test("account senza leghe: l'Asta mostra lo stato vuoto (corsa M4, 22/11)", () => {
  assert.equal(auctionHubHasLeague(null), false);
  assert.equal(auctionHubHasLeague(undefined), false);
  assert.equal(auctionHubHasLeague(""), false);
  assert.equal(auctionHubHasLeague("lega-1"), true);
});

test("senza lega l'Asta non monta barra del mercato, schede e «Configura asta»", () => {
  const source = readFileSync(new URL("./AuctionHubScreen.tsx", import.meta.url), "utf8");
  const branch = source.indexOf("auctionHubHasLeague(activeLeagueId) ? (");
  const empty = source.indexOf('testID="auction-no-league"');
  assert.ok(branch > 0 && empty > branch, "manca lo stato vuoto senza lega");
  // Barra del mercato e sottoschede (con «Live» e il suo «Configura asta») solo nel ramo con la lega.
  for (const piece of ["<MarketGateBar />", "<AuctionLiveScreen", 'testID="auction-mode-tabs"']) {
    const at = source.indexOf(piece);
    assert.ok(at > branch && at < empty, piece);
  }
});
