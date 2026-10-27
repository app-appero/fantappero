import assert from "node:assert/strict";
import test from "node:test";
import { resolveNotificationRoute } from "./notificationDestination.ts";

test("le notifiche di scambio aprono Scambi", () => {
  assert.deepEqual(resolveNotificationRoute({ title: "Nuova proposta di scambio", deepLink: "/mercato" }), { kind: "tab", screen: "Market" });
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
