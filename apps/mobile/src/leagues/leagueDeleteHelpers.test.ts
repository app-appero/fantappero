import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { describe, it } from "node:test";
import { isLeagueDeletable, stackAfterLeagueDeleted } from "./leagueDeleteHelpers.ts";

describe("isLeagueDeletable", () => {
  it("allows draft and configuring only", () => {
    assert.equal(isLeagueDeletable("draft"), true);
    assert.equal(isLeagueDeletable("configuring"), true);
    assert.equal(isLeagueDeletable("auction"), false);
    assert.equal(isLeagueDeletable("active"), false);
    assert.equal(isLeagueDeletable("concluded"), false);
    assert.equal(isLeagueDeletable("archived"), false);
    assert.equal(isLeagueDeletable(undefined), false);
  });
});

describe("dopo «Elimina lega» indietro non torna sulla lega eliminata (QA 23/11)", () => {
  it("la pila riparte da schede e Home lega, senza Amministrazione", () => {
    const stack = stackAfterLeagueDeleted();
    assert.deepEqual(
      stack.routes.map((route) => route.name),
      ["MainTabs", "LeagueHome"],
    );
    assert.equal(stack.index, stack.routes.length - 1);
    // La Home lega senza parametri apre la lega rimasta attiva, non l'id eliminato.
    assert.ok(stack.routes.every((route) => !("params" in route)));
  });

  it("Amministrazione lega azzera la pila invece di aggiungere la Home sopra", () => {
    const source = readFileSync(new URL("../screens/LeagueAdminScreen.tsx", import.meta.url), "utf8");
    const start = source.indexOf("  async function onDelete() {");
    const end = source.indexOf("\n  }\n", start);
    assert.ok(start >= 0 && end > start, "manca onDelete");
    const body = source.slice(start, end);
    assert.match(body, /navigation\.reset\(stackAfterLeagueDeleted\(\)\)/);
    assert.doesNotMatch(body, /navigation\.navigate\("LeagueHome"\)/);
  });
});
