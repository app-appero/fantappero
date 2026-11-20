import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { coachProfileAccessibilityLabel, visibleCoachEmail } from "./coachEmail.ts";

describe("visibleCoachEmail", () => {
  it("mostra l'email quando il backend la manda (admin della lega o operatore)", () => {
    assert.equal(visibleCoachEmail({ email: "g.trotta@example.com" }), "g.trotta@example.com");
    assert.equal(visibleCoachEmail({ email: "  g.trotta@example.com " }), "g.trotta@example.com");
  });

  it("non mostra nulla a chi non la riceve, né con i backend precedenti", () => {
    assert.equal(visibleCoachEmail({ email: null }), null);
    assert.equal(visibleCoachEmail({}), null);
    assert.equal(visibleCoachEmail({ email: "   " }), null);
  });

  it("distingue due fantallenatori con lo stesso nome", () => {
    const first = { displayName: "Giuseppe Trotta", email: "giuseppe.trotta@example.com" };
    const second = { displayName: "Giuseppe Trotta", email: "gtrotta82@example.com" };
    assert.notEqual(visibleCoachEmail(first), visibleCoachEmail(second));
  });
});

describe("coachProfileAccessibilityLabel", () => {
  it("aggiunge l'email quando è visibile", () => {
    assert.equal(
      coachProfileAccessibilityLabel({
        displayName: "Giuseppe Trotta",
        email: "giuseppe.trotta@example.com",
      }),
      "Apri il profilo di Giuseppe Trotta (giuseppe.trotta@example.com)",
    );
  });

  it("senza email resta l'etichetta di prima", () => {
    assert.equal(
      coachProfileAccessibilityLabel({ displayName: "Giuseppe Trotta", email: null }),
      "Apri il profilo di Giuseppe Trotta",
    );
    assert.equal(
      coachProfileAccessibilityLabel({ displayName: "Giuseppe Trotta" }),
      "Apri il profilo di Giuseppe Trotta",
    );
  });
});
