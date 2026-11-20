import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { csvResolutionPayload, toggleCsvResolution } from "./csvImportResolutions.ts";

describe("toggleCsvResolution", () => {
  it("chooses a candidate, switches to another and clears on a second tap", () => {
    const chosen = toggleCsvResolution({}, 3, "barca");
    assert.deepEqual(chosen, { 3: "barca" });
    const switched = toggleCsvResolution(chosen, 3, "venezia");
    assert.deepEqual(switched, { 3: "venezia" });
    assert.deepEqual(toggleCsvResolution(switched, 3, "venezia"), {});
  });

  it("leaves the other rows and the original object untouched", () => {
    const original = { 2: "a", 5: "b" };
    assert.deepEqual(toggleCsvResolution(original, 5, "c"), { 2: "a", 5: "c" });
    assert.deepEqual(original, { 2: "a", 5: "b" });
  });
});

describe("csvResolutionPayload", () => {
  it("sends only the choices made, ordered by row", () => {
    assert.deepEqual(csvResolutionPayload({ 7: "x", 3: "y", 4: "" }), [
      { rowNumber: 3, athleteId: "y" },
      { rowNumber: 7, athleteId: "x" },
    ]);
    assert.deepEqual(csvResolutionPayload({}), []);
  });
});
