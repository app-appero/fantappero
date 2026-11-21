import assert from "node:assert/strict";
import { beforeEach, describe, it } from "node:test";
import { readLastScreen, rememberLastScreen } from "../feedback/lastScreen.ts";
import { focusedRouteName, type NavigationStateLike } from "./focusedRoute.ts";

function tabs(index: number | undefined): NavigationStateLike {
  return {
    type: "tab",
    index,
    routes: [{ name: "Matchday" }, { name: "Standings" }, { name: "Roster" }, { name: "Profile" }],
  };
}

function root(routes: NavigationStateLike["routes"], index = routes.length - 1): NavigationStateLike {
  return { type: "stack", index, routes };
}

describe("pagina di «Segnala un problema»: schermata a fuoco in tutto l'albero (Rosario 21/11)", () => {
  it("la tab a fuoco dentro MainTabs, qualunque sia la strada (menu, Home lega, notifica)", () => {
    assert.equal(focusedRouteName(root([{ name: "MainTabs", state: tabs(2) }])), "Roster");
    assert.equal(focusedRouteName(root([{ name: "MainTabs", state: tabs(0) }])), "Matchday");
  });

  it("le schermate dello stack sopra le tab (es. Home lega) si riportano col loro nome", () => {
    const state = root([{ name: "MainTabs", state: tabs(2) }, { name: "LeagueHome" }]);
    assert.equal(focusedRouteName(state), "LeagueHome");
    const matchup = root([{ name: "MainTabs", state: tabs(0) }, { name: "MatchupDetail" }]);
    assert.equal(focusedRouteName(matchup), "MatchupDetail");
  });

  it("scende in profondità anche nel pannello admin", () => {
    const admin: NavigationStateLike = {
      type: "stack",
      index: 1,
      routes: [{ name: "AdminHome" }, { name: "AdminFeedback" }],
    };
    const state = root([{ name: "MainTabs", state: tabs(2) }, { name: "AdminPanel", state: admin }]);
    assert.equal(focusedRouteName(state), "AdminFeedback");
  });

  it("stato delle tab non ancora noto: nessuna pagina, mai «Matchday» per ripiego", () => {
    assert.equal(focusedRouteName(root([{ name: "MainTabs" }])), undefined);
    assert.equal(focusedRouteName(root([{ name: "MainTabs", state: tabs(undefined) }])), undefined);
    assert.equal(focusedRouteName(root([{ name: "AdminPanel" }])), undefined);
    assert.equal(focusedRouteName(undefined), undefined);
    assert.equal(focusedRouteName(root([{ name: "MainTabs", state: tabs(9) }])), undefined);
    assert.equal(focusedRouteName({ index: 0, routes: [] }), undefined);
  });

  it("stato parziale di uno stack senza indice: a fuoco è l'ultima schermata", () => {
    const partial: NavigationStateLike = {
      type: "stack",
      routes: [{ name: "MainTabs", state: tabs(2) }, { name: "Notifications" }],
    };
    assert.equal(focusedRouteName(partial), "Notifications");
  });
});

describe("ultima schermata ricordata per la segnalazione", () => {
  beforeEach(() => {
    rememberLastScreen(undefined);
  });

  it("aprire «Segnala un problema» non sostituisce la schermata di prima", () => {
    rememberLastScreen("Roster");
    rememberLastScreen("Feedback");
    assert.equal(readLastScreen(), "Roster");
  });

  it("una schermata sconosciuta dimentica quella vecchia invece di riportarla", () => {
    rememberLastScreen("Matchday");
    rememberLastScreen(undefined);
    assert.equal(readLastScreen(), undefined);
  });

  it("segue l'ultima schermata vista", () => {
    rememberLastScreen("LeagueHome");
    rememberLastScreen("Roster");
    assert.equal(readLastScreen(), "Roster");
  });
});
