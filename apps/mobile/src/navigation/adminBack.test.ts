import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { ADMIN_BACK_LABEL, ADMIN_SCREEN_BY_ID, adminBackTarget } from "./adminScreens.ts";

describe("pannello operatore: tasto «Indietro» (1.5)", () => {
  it("si chiama «Indietro»", () => {
    assert.equal(ADMIN_BACK_LABEL, "Indietro");
  });

  it("da una sezione torna indietro nella pila, o al Riepilogo se non c'è nulla prima", () => {
    assert.equal(adminBackTarget({ screen: "AdminListone", canGoBack: true }), "back");
    assert.equal(adminBackTarget({ screen: "AdminListone", canGoBack: false }), "home");
    assert.equal(adminBackTarget({ screen: "AdminEmail", canGoBack: false }), "home");
  });

  it("dal Riepilogo si esce dal pannello e si torna all'app", () => {
    assert.equal(adminBackTarget({ screen: "AdminHome", canGoBack: false }), "app");
    assert.equal(adminBackTarget({ screen: "AdminHome", canGoBack: true }), "app");
  });

  it("ogni sezione del menù ha un «Indietro»", () => {
    for (const screen of Object.values(ADMIN_SCREEN_BY_ID)) {
      const target = adminBackTarget({ screen, canGoBack: true });
      assert.equal(target, screen === "AdminHome" ? "app" : "back");
    }
  });
});
