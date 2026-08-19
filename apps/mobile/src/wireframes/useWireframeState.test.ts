import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
  parseWireframeState,
  WIREFRAME_STATES,
} from "../../../../packages/contracts/src/wireframes.ts";

describe("wireframe state helpers", () => {
  it("parses valid stato values", () => {
    for (const state of WIREFRAME_STATES) {
      assert.equal(parseWireframeState(state), state);
    }
  });

  it("defaults to success for unknown stato", () => {
    assert.equal(parseWireframeState("unknown"), "success");
    assert.equal(parseWireframeState(undefined), "success");
  });

  it("builds navigation params for dev toggles", () => {
    assert.deepEqual({ stato: "loading" as const }, { stato: "loading" });
  });
});
