import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { describe, it } from "node:test";
import { rulesSavedMessage } from "./rulesSaved.ts";

/** Corpo di `async function onSaveRules()` in Amministrazione lega. */
function onSaveRulesBody(): string {
  const source = readFileSync(new URL("../screens/LeagueAdminScreen.tsx", import.meta.url), "utf8");
  const start = source.indexOf("  async function onSaveRules() {");
  assert.ok(start >= 0, "manca onSaveRules");
  const end = source.indexOf("\n  }\n", start);
  assert.ok(end > start, "onSaveRules non chiusa");
  return source.slice(start, end);
}

describe("Amministrazione lega › «Salva regolamento» (corsa M4, 22/11)", () => {
  it("al primo salvataggio la conferma dice dove si invitano i fantallenatori", () => {
    assert.match(rulesSavedMessage(true), /scheda «Invitati»/);
    assert.equal(rulesSavedMessage(false), "Le modifiche sono state applicate.");
  });

  it("dopo il salvataggio si resta sul regolamento, senza passare a «Invitati»", () => {
    const body = onSaveRulesBody();
    assert.doesNotMatch(body, /setSetupTab\(/);
    assert.match(body, /setSaveSuccess\(rulesSavedMessage\(!configurationSaved\)\)/);
  });

  it("la conferma sta nella scheda del regolamento, sopra il pulsante", () => {
    const source = readFileSync(new URL("../screens/LeagueAdminScreen.tsx", import.meta.url), "utf8");
    const saved = source.indexOf('testID="league-admin-rules-saved"');
    const button = source.indexOf('testID="league-admin-save-rules"');
    const rulesTab = source.indexOf('{setupTab === "configurazione" ? (');
    const invitesTab = source.indexOf('{setupTab === "invitati" ? (');
    assert.ok(rulesTab >= 0 && rulesTab < saved && saved < button && button < invitesTab);
    assert.match(source, /message=\{saveSuccess\}/);
  });
});
