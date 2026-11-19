import assert from "node:assert/strict";
import { describe, it } from "node:test";

import {
  AUTH_TABS,
  INITIAL_AUTH_TAB,
  isEmailCardExpanded,
  resolveAuthLayout,
  resolveAuthScreenView,
  type AuthScreenInput,
} from "./authScreenState.ts";

const base: AuthScreenInput = {
  optionsLoaded: true,
  emailRegistrationEnabled: true,
  googleAvailable: true,
  expandedChoice: null,
};

describe("resolveAuthLayout", () => {
  it("registrazione email spenta: solo Google, come oggi", () => {
    assert.equal(resolveAuthLayout({ ...base, emailRegistrationEnabled: false }), "google");
    assert.equal(resolveAuthLayout({ ...base, emailRegistrationEnabled: false, googleAvailable: false }), "google");
  });

  it("finché il server non risponde resta solo Google", () => {
    assert.equal(resolveAuthLayout({ ...base, optionsLoaded: false }), "google");
  });

  it("registrazione email accesa: Google più email, oppure solo email se Google manca", () => {
    assert.equal(resolveAuthLayout(base), "google_email");
    assert.equal(resolveAuthLayout({ ...base, googleAvailable: false }), "email");
  });
});

describe("isEmailCardExpanded", () => {
  it("con Google la scheda parte chiusa, senza Google parte aperta", () => {
    assert.equal(isEmailCardExpanded("google_email", null), false);
    assert.equal(isEmailCardExpanded("email", null), true);
  });

  it("vale la scelta dell'utente", () => {
    assert.equal(isEmailCardExpanded("google_email", true), true);
    assert.equal(isEmailCardExpanded("email", false), false);
  });

  it("solo Google: mai aperta, anche con una scelta rimasta", () => {
    assert.equal(isEmailCardExpanded("google", true), false);
  });
});

describe("resolveAuthScreenView", () => {
  it("solo Google: carte, nota sotto Google, niente email", () => {
    const view = resolveAuthScreenView({ ...base, emailRegistrationEnabled: false });
    assert.deepEqual(view, {
      layout: "google",
      emailExpanded: false,
      showEmailToggle: false,
      showEmailCard: false,
      dividerLabel: null,
      showCardsStage: true,
      showGoogleNote: true,
    });
  });

  it("Google più email, chiusa: «oppure» e il tasto «Continua con email», niente modulo", () => {
    const view = resolveAuthScreenView(base);
    assert.equal(view.layout, "google_email");
    assert.equal(view.dividerLabel, "oppure");
    assert.equal(view.showEmailToggle, true);
    assert.equal(view.showEmailCard, false);
    assert.equal(view.showCardsStage, true);
    assert.equal(view.showGoogleNote, false);
  });

  it("Google più email, aperta: «oppure con email», scheda e carte nascoste", () => {
    const view = resolveAuthScreenView({ ...base, expandedChoice: true });
    assert.equal(view.dividerLabel, "oppure con email");
    assert.equal(view.showEmailToggle, false);
    assert.equal(view.showEmailCard, true);
    assert.equal(view.showCardsStage, false);
  });

  it("richiusa dall'utente torna come all'inizio", () => {
    assert.deepEqual(resolveAuthScreenView({ ...base, expandedChoice: false }), resolveAuthScreenView(base));
  });

  it("Google non configurato: scheda già aperta e nessun separatore", () => {
    const view = resolveAuthScreenView({ ...base, googleAvailable: false });
    assert.equal(view.layout, "email");
    assert.equal(view.showEmailCard, true);
    assert.equal(view.showEmailToggle, false);
    assert.equal(view.dividerLabel, null);
    assert.equal(view.showGoogleNote, false);
  });

  it("il vecchio modulo sempre aperto non c'è mai con Google e registrazione accesa", () => {
    const view = resolveAuthScreenView(base);
    assert.equal(view.showEmailCard, false);
  });

  it("Google non configurato e registrazione spenta: come oggi, nessuna email", () => {
    const view = resolveAuthScreenView({ ...base, emailRegistrationEnabled: false, googleAvailable: false });
    assert.equal(view.showEmailCard, false);
    assert.equal(view.showEmailToggle, false);
    assert.equal(view.showGoogleNote, false);
  });
});

describe("schede Accedi / Registrati", () => {
  it("due schede, Accedi per prima e iniziale", () => {
    assert.deepEqual(
      AUTH_TABS.map((tab) => [tab.key, tab.label, tab.testID]),
      [
        ["accedi", "Accedi", "auth-tab-login"],
        ["registrati", "Registrati", "auth-tab-register"],
      ],
    );
    assert.equal(INITIAL_AUTH_TAB, "accedi");
  });
});
