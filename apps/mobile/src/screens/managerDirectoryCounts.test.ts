import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { describe, it } from "node:test";
import { directoryCountsRequest } from "./managerDirectoryCounts.ts";

describe("Fantallenatori aperti da un partecipante (QA 22→23/11)", () => {
  it("il partecipante non chiede i conteggi da amministratore (prima: due 403)", () => {
    assert.equal(directoryCountsRequest({ isAdmin: false, accessToken: "token", leagueId: "lega-1" }), null);
  });

  it("l'amministratore li chiede per la lega attiva", () => {
    assert.deepEqual(directoryCountsRequest({ isAdmin: true, accessToken: "token", leagueId: "lega-1" }), {
      accessToken: "token",
      leagueId: "lega-1",
    });
  });

  it("senza sessione o senza lega attiva non si chiede nulla", () => {
    assert.equal(directoryCountsRequest({ isAdmin: true, accessToken: null, leagueId: "lega-1" }), null);
    assert.equal(directoryCountsRequest({ isAdmin: true, accessToken: "token", leagueId: null }), null);
    assert.equal(directoryCountsRequest({ isAdmin: true, accessToken: "", leagueId: undefined }), null);
  });

  it("la schermata passa dal permesso prima di ogni chiamata", () => {
    const source = readFileSync(new URL("./ManagerDirectoryScreen.tsx", import.meta.url), "utf8");
    const guarded = source.match(/directoryCountsRequest\(\{ isAdmin, accessToken, leagueId: activeLeagueId \}\)/g) ?? [];
    assert.equal(guarded.length, 2, "amministrazione/partecipanti e stato del mercato");
    for (const call of ["fetchLeagueAdminPanel", "fetchLeagueMembers", "fetchMarketGate"]) {
      assert.match(source, new RegExp(`${call}\\(request\\.accessToken, request\\.leagueId\\)`), call);
    }
  });
});
