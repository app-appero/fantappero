import assert from "node:assert/strict";
import test from "node:test";
import { impersonationTab, planNotificationOpen, resolveNotificationRoute } from "./notificationDestination.ts";

test("le notifiche di scambio aprono Scambi", () => {
  assert.deepEqual(resolveNotificationRoute({ title: "Nuova proposta di scambio", deepLink: "/mercato" }), { kind: "tab", screen: "Market" });
});

test("le notifiche di scambio con l'id della proposta aprono quella specifica", () => {
  assert.deepEqual(
    resolveNotificationRoute({ title: "Controproposta ricevuta", deepLink: "/mercato?scambio=abc-123" }),
    { kind: "tab", screen: "Market", params: { scambio: "abc-123" } },
  );
});

test("le notifiche di scambio col titolo dinamico (v2, nome squadra) aprono comunque Scambi", () => {
  assert.deepEqual(
    resolveNotificationRoute({
      title: "Squadra Sfidante ti propone uno scambio",
      deepLink: "/mercato?scambio=abc-123",
    }),
    { kind: "tab", screen: "Market", params: { scambio: "abc-123" } },
  );
  assert.deepEqual(
    resolveNotificationRoute({
      title: "Squadra Sfidante ha rifiutato lo scambio",
      deepLink: "/mercato?scambio=xyz-789",
    }),
    { kind: "tab", screen: "Market", params: { scambio: "xyz-789" } },
  );
});

test("le notifiche d'asta aprono Asta", () => {
  assert.deepEqual(resolveNotificationRoute({ title: "Sei stato sorpassato", deepLink: "/mercato" }), { kind: "tab", screen: "Auction" });
});

test("le notifiche dell'asta a rilanci aprono la scheda «Live» dell'Asta", () => {
  const titles = [
    "Asta a rilanci iniziata",
    "Lotto aggiudicato",
    "Sei stato sorpassato",
    "Scelta richiesta: rosa al completo",
    "Lotto perso: crediti insufficienti",
    "Lotto perso: rosa al completo",
  ];
  for (const title of titles) {
    assert.deepEqual(
      resolveNotificationRoute({ title, deepLink: "/asta-live?lega=league-1" }),
      { kind: "tab", screen: "Auction", params: { modalita: "live" } },
      title,
    );
  }
});

test("le notifiche delle buste chiuse aprono la scheda «Buste chiuse» dell'Asta", () => {
  for (const title of ["Busta aggiudicata", "Busta non aggiudicata", "Spareggio aperto", "Spareggio annullato"]) {
    assert.deepEqual(
      resolveNotificationRoute({ title, deepLink: "/asta?lega=league-1" }),
      { kind: "tab", screen: "Auction", params: { modalita: "buste" } },
      title,
    );
  }
});

test("gli esiti degli svincolati aprono la schermata Svincolati, non l'Asta (QA 19-20/11)", () => {
  for (const title of [
    "Svincolato aggiudicato",
    "Svincolato perso",
    "Spareggio svincolati aperto",
    "Spareggio svincolati annullato",
  ]) {
    assert.deepEqual(
      resolveNotificationRoute({ title, deepLink: "/svincolati?lega=league-1" }),
      { kind: "tab", screen: "Waiver" },
      title,
    );
  }
  // Anche il percorso della pagina web («/svincoli», es. contesto di una segnalazione).
  assert.deepEqual(resolveNotificationRoute({ title: "x", deepLink: "/svincoli" }), { kind: "tab", screen: "Waiver" });
  assert.equal(impersonationTab("/svincoli"), "Waiver");
});

test("i percorsi web dell'asta scelgono la modalità anche senza titolo noto", () => {
  assert.deepEqual(resolveNotificationRoute({ title: "x", deepLink: "/asta-live" }), {
    kind: "tab",
    screen: "Auction",
    params: { modalita: "live" },
  });
  assert.deepEqual(resolveNotificationRoute({ title: "x", deepLink: "/asta" }), {
    kind: "tab",
    screen: "Auction",
    params: { modalita: "buste" },
  });
  assert.equal(impersonationTab("/asta-live"), "Auction");
});

test("deep link interni mappati sulle schermate dell'app", () => {
  assert.deepEqual(resolveNotificationRoute({ title: "x", deepLink: "/formazione?turno=3" }), { kind: "tab", screen: "Formation" });
  assert.deepEqual(resolveNotificationRoute({ title: "x", deepLink: "/inviti" }), { kind: "stack", name: "ReceivedInvites" });
});

test("esito invito e nuovo partecipante aprono la directory fantallenatori", () => {
  for (const title of ["Invito accettato", "Invito rifiutato", "Nuovo partecipante in lega"]) {
    assert.deepEqual(
      resolveNotificationRoute({ title, deepLink: "/fantallenatori?lega=league-1" }),
      { kind: "stack", name: "ManagerDirectory" },
    );
  }
  assert.deepEqual(resolveNotificationRoute({ title: "x", deepLink: "/fantallenatori" }), {
    kind: "stack",
    name: "ManagerDirectory",
  });
});

test("«La lega è al completo» apre l'amministrazione della lega (20/11)", () => {
  assert.deepEqual(
    resolveNotificationRoute({
      title: "La lega è al completo: puoi aprire il mercato",
      deepLink: "/lega/amministrazione?lega=league-1",
    }),
    { kind: "stack", name: "LeagueAdmin", params: { leagueId: "league-1" } },
  );
  assert.deepEqual(resolveNotificationRoute({ title: "x", deepLink: "/lega/amministrazione" }), {
    kind: "stack",
    name: "LeagueAdmin",
  });
});

test("senza meta noto non naviga", () => {
  assert.equal(resolveNotificationRoute({ title: "x", deepLink: null }), null);
  assert.equal(resolveNotificationRoute({ title: "x", deepLink: "https://evil.example" }), null);
});

test("il deep link di un evento calciatore apre lo scontro tra fantallenatori", () => {
  assert.deepEqual(
    resolveNotificationRoute({ title: "Gol", deepLink: "/turni/scontro/abc-123" }),
    { kind: "matchup", slotId: "abc-123" },
  );
  assert.deepEqual(resolveNotificationRoute({ title: "Gol", deepLink: "/turni" }), { kind: "tab", screen: "Matchday" });
});

test("la notifica di una nuova segnalazione apre la schermata operatore", () => {
  assert.deepEqual(
    resolveNotificationRoute({ title: "Nuovo bug da Mario", deepLink: "/admin/feedback" }),
    { kind: "admin", screen: "AdminFeedback" },
  );
});

test("la notifica di una nuova richiesta tester apre la schermata utenti operatore", () => {
  assert.deepEqual(
    resolveNotificationRoute({ title: "Nuova richiesta di accesso al pilota", deepLink: "/admin/utenti" }),
    { kind: "admin", screen: "AdminUsers" },
  );
});

test("impersonificazione: nome di schermata o percorso web aprono la tab giusta", () => {
  assert.equal(impersonationTab("Formation"), "Formation");
  assert.equal(impersonationTab(" Standings "), "Standings");
  assert.equal(impersonationTab("/formazione"), "Formation");
  assert.equal(impersonationTab("/classifica"), "Standings");
});

test("impersonificazione: contesto assente, sconosciuto o esterno apre la tab iniziale", () => {
  for (const value of [null, undefined, "", "LeagueAdmin", "https://evil.example", "/admin/feedback"]) {
    assert.equal(impersonationTab(value), undefined);
  }
});

test("l'avviso di stato di una propria segnalazione apre «Segnala un problema»", () => {
  assert.deepEqual(
    resolveNotificationRoute({ title: "La tua segnalazione è stata risolta", deepLink: "/feedback" }),
    { kind: "stack", name: "Feedback" },
  );
});

// -- Lega della notifica (Rosario 21/11): prima si rende attiva, poi si naviga. ----------------

const IN_A_AND_B = {
  activeLeagueId: "league-b",
  leagues: [{ id: "league-a" }, { id: "league-b" }],
};

test("tocco su una notifica della lega A con attiva la B: prima la lega A, poi la schermata", () => {
  assert.deepEqual(
    planNotificationOpen(
      { title: "Squadra X ti propone uno scambio", deepLink: "/mercato?scambio=p-1&lega=league-a" },
      IN_A_AND_B,
    ),
    {
      route: { kind: "tab", screen: "Market", params: { scambio: "p-1" } },
      switchToLeagueId: "league-a",
    },
  );
});

test("ogni deep link di lega del backend cambia la lega attiva prima di aprire la schermata", () => {
  // Percorsi di notifications/templates.py con `_league_link`: in app e nei dati della push.
  const cases: Array<[string, string]> = [
    ["Blocco formazione in arrivo", "/formazione?lega=league-a"],
    ["Scadenza formazione in arrivo", "/formazione?lega=league-a"],
    ["Turno 8 aperto", "/formazione?lega=league-a"],
    ["Busta aggiudicata", "/asta?lega=league-a"],
    ["Sei stato sorpassato", "/asta-live?lega=league-a"],
    ["Svincolato aggiudicato", "/svincolati?lega=league-a"],
    ["Scambio con Squadra X approvato", "/mercato?scambio=p-1&lega=league-a"],
    ["Turno omologato", "/classifica?lega=league-a"],
    ["Gol di Lautaro", "/turni?lega=league-a"],
    ["Gol di Lautaro", "/turni/scontro/slot-1?lega=league-a"],
    ["Invito accettato", "/fantallenatori?lega=league-a"],
    ["Nuovo partecipante in lega", "/fantallenatori?lega=league-a"],
    ["La lega è al completo: puoi aprire il mercato", "/lega/amministrazione?lega=league-a"],
    ["La lega è partita", "/?lega=league-a"],
  ];
  for (const [title, deepLink] of cases) {
    const plan = planNotificationOpen({ title, deepLink }, IN_A_AND_B);
    assert.ok(plan, deepLink);
    assert.deepEqual(plan.route, resolveNotificationRoute({ title, deepLink }), deepLink);
    assert.equal(plan.switchToLeagueId, "league-a", deepLink);
  }
  // Lo scontro e l'amministrazione restano quelli della notifica.
  assert.deepEqual(
    planNotificationOpen({ title: "Gol", deepLink: "/turni/scontro/slot-1?lega=league-a" }, IN_A_AND_B)?.route,
    { kind: "matchup", slotId: "slot-1" },
  );
  assert.deepEqual(
    planNotificationOpen({ title: "x", deepLink: "/lega/amministrazione?lega=league-a" }, IN_A_AND_B)?.route,
    { kind: "stack", name: "LeagueAdmin", params: { leagueId: "league-a" } },
  );
});

test("notifica della lega già attiva: nessun cambio di lega", () => {
  assert.deepEqual(planNotificationOpen({ title: "x", deepLink: "/formazione?lega=league-b" }, IN_A_AND_B), {
    route: { kind: "tab", screen: "Formation" },
    switchToLeagueId: null,
  });
});

test("lega di cui non si fa più parte: si apre come prima, nella lega attiva", () => {
  assert.deepEqual(planNotificationOpen({ title: "x", deepLink: "/classifica?lega=league-lasciata" }, IN_A_AND_B), {
    route: { kind: "tab", screen: "Standings" },
    switchToLeagueId: null,
  });
  // Nessuna lega caricata (es. elenco non disponibile): nessun cambio, nessun errore.
  assert.deepEqual(
    planNotificationOpen({ title: "x", deepLink: "/classifica?lega=league-a" }, { activeLeagueId: null, leagues: [] }),
    { route: { kind: "tab", screen: "Standings" }, switchToLeagueId: null },
  );
});

test("notifiche senza lega (inviti, lega eliminata, operatori): solo la navigazione", () => {
  for (const deepLink of ["/inviti", "/", "/admin/feedback", "/feedback"]) {
    const plan = planNotificationOpen({ title: "x", deepLink }, IN_A_AND_B);
    assert.ok(plan, deepLink);
    assert.equal(plan.switchToLeagueId, null, deepLink);
  }
  // Notifica vecchia senza deep link: meta dal titolo, lega attiva invariata.
  assert.deepEqual(planNotificationOpen({ title: "Turno omologato", deepLink: null }, IN_A_AND_B), {
    route: { kind: "tab", screen: "Standings" },
    switchToLeagueId: null,
  });
});

test("senza meta o con un link esterno non cambia nulla, nemmeno la lega", () => {
  assert.equal(planNotificationOpen({ title: "x", deepLink: "/pagina-sconosciuta?lega=league-a" }, IN_A_AND_B), null);
  assert.equal(planNotificationOpen({ title: "x", deepLink: "https://evil.example/?lega=league-a" }, IN_A_AND_B), null);
  assert.equal(planNotificationOpen({ title: "x", deepLink: null }, IN_A_AND_B), null);
});

test("release 1.4: «È disponibile la versione X dell'app» apre il link di download", () => {
  const item = {
    title: "È disponibile la versione 1.4 dell'app",
    deepLink: "https://drive.google.com/drive/folders/fantappero-1-4",
  };
  assert.deepEqual(resolveNotificationRoute(item), {
    kind: "external",
    url: "https://drive.google.com/drive/folders/fantappero-1-4",
  });
  // Nessun cambio di lega: è un link esterno.
  assert.deepEqual(planNotificationOpen(item, { activeLeagueId: "a", leagues: [{ id: "a" }] }), {
    route: { kind: "external", url: "https://drive.google.com/drive/folders/fantappero-1-4" },
    switchToLeagueId: null,
  });
});

test("solo la notifica della nuova versione apre un link esterno, e solo https", () => {
  const title = "È disponibile la versione 1.4 dell'app";
  for (const deepLink of ["http://example.com/app.apk", "javascript:alert(1)", "https://", "https://a b"]) {
    assert.equal(resolveNotificationRoute({ title, deepLink }), null, deepLink);
  }
  // Un'altra notifica con un link esterno resta senza meta.
  assert.equal(resolveNotificationRoute({ title: "Avviso", deepLink: "https://drive.google.com/x" }), null);
  assert.deepEqual(
    resolveNotificationRoute({ title: "È disponibile una nuova versione dell'app", deepLink: "https://x.example/a" }),
    { kind: "external", url: "https://x.example/a" },
  );
});

test("1.5: «Scegli il sostituto dopo lo scambio» apre Rosa con la scelta, nella lega dello scambio", () => {
  const item = {
    title: "Scegli il sostituto dopo lo scambio",
    deepLink: "/rosa?sostituto=1&lega=league-2",
  };
  assert.deepEqual(resolveNotificationRoute(item), {
    kind: "tab",
    screen: "Roster",
    params: { sostituto: "1" },
  });
  assert.deepEqual(
    planNotificationOpen(item, { activeLeagueId: "league-1", leagues: [{ id: "league-1" }, { id: "league-2" }] }),
    { route: { kind: "tab", screen: "Roster", params: { sostituto: "1" } }, switchToLeagueId: "league-2" },
  );
  // Rosa senza il parametro resta la Rosa di sempre.
  assert.deepEqual(resolveNotificationRoute({ title: "x", deepLink: "/rosa?lega=league-2" }), {
    kind: "tab",
    screen: "Roster",
  });
});
