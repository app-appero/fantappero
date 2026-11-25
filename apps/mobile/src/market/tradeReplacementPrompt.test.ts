import assert from "node:assert/strict";
import test from "node:test";
import {
  markReplacementPromptShown,
  replacementPromptShown,
  resetReplacementPromptMemory,
  wantsReplacementSheet,
} from "./tradeReplacementPrompt.ts";

test("1.5: la scelta del sostituto si apre da sola una volta per sessione, per lega", () => {
  resetReplacementPromptMemory();
  assert.equal(replacementPromptShown("league-1"), false);
  markReplacementPromptShown("league-1");
  assert.equal(replacementPromptShown("league-1"), true);
  assert.equal(replacementPromptShown("league-2"), false);
  // Riavvio dell'app: si riapre.
  resetReplacementPromptMemory();
  assert.equal(replacementPromptShown("league-1"), false);
});

test("1.5: il link della notifica chiede di aprire la scelta", () => {
  assert.equal(wantsReplacementSheet({ sostituto: "1" }), true);
  assert.equal(wantsReplacementSheet({ sostituto: "0" }), false);
  assert.equal(wantsReplacementSheet({}), false);
  assert.equal(wantsReplacementSheet(undefined), false);
});
