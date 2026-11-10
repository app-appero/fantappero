import assert from "node:assert/strict";
import test from "node:test";
import { impersonationTab, resolveNotificationRoute } from "./notificationDestination.ts";

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

test("deep link interni mappati sulle schermate dell'app", () => {
  assert.deepEqual(resolveNotificationRoute({ title: "x", deepLink: "/formazione?turno=3" }), { kind: "tab", screen: "Formation" });
  assert.deepEqual(resolveNotificationRoute({ title: "x", deepLink: "/inviti" }), { kind: "stack", name: "ReceivedInvites" });
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
