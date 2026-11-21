import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { pushNotificationsAvailable } from "./pushSupport.ts";

describe("pushNotificationsAvailable", () => {
  it("accese in una build vera per Android e iOS", () => {
    assert.equal(pushNotificationsAvailable("android", false), true);
    assert.equal(pushNotificationsAvailable("ios", false), true);
  });

  it("spente nel browser: niente errore di expo-notifications a ogni avvio (QA 20-21/11)", () => {
    assert.equal(pushNotificationsAvailable("web", false), false);
  });

  it("spente in Expo Go, che non ha il modulo nativo", () => {
    assert.equal(pushNotificationsAvailable("android", true), false);
    assert.equal(pushNotificationsAvailable("ios", true), false);
  });
});
