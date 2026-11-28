import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { usersLabel } from "./confirmations.ts";
import { evaluateLineup } from "./fantasyLineups.ts";
import { countWithNoun, missingCount, missingStartersLabel, pendingInvitesA11yLabel } from "./plural.ts";

describe("singolare con 1 (QA 24-25/11)", () => {
  it("accorda la parola al numero", () => {
    assert.equal(countWithNoun(1, "titolare", "titolari"), "1 titolare");
    assert.equal(countWithNoun(0, "titolare", "titolari"), "0 titolari");
    assert.equal(countWithNoun(4, "titolare", "titolari"), "4 titolari");
    assert.equal(missingCount(1), "manca 1");
    assert.equal(missingCount(2), "mancano 2");
  });

  it("destinatari di notifiche ed email: «1 utente», mai «1 utenti» (QA 28/11)", () => {
    assert.equal(usersLabel(1), "1 utente");
    assert.equal(usersLabel(0), "0 utenti");
    assert.equal(usersLabel(2), "2 utenti");
    assert.equal(usersLabel(1200), "1200 utenti");
    assert.equal(usersLabel(null), "tutti gli utenti");
  });

  it("badge inviti ricevuti", () => {
    assert.equal(pendingInvitesA11yLabel(1), "1 invito in attesa di risposta");
    assert.equal(pendingInvitesA11yLabel(3), "3 inviti in attesa di risposta");
  });

  it("pulsante della formazione incompleta", () => {
    assert.equal(missingStartersLabel(1), "Manca 1 titolare");
    assert.equal(missingStartersLabel(5), "Mancano 5 titolari");
  });

  it("il controllo della panchina non dice «mancano 1 in panchina»", () => {
    const starters = ["P1", "D1", "D2", "D3", "D4", "C1", "C2", "C3", "A1", "A2", "A3"];
    const roles: Record<string, "P" | "D" | "C" | "A"> = {};
    for (const id of [...starters, "X1", "X2"]) {
      roles[id] = id[0] === "X" ? "C" : (id[0] as "P" | "D" | "C" | "A");
    }
    const messages = (unused: string[]) =>
      evaluateLineup({
        module: "4-3-3",
        starters: starters.map((athleteId) => ({ athleteId, role: roles[athleteId]! })),
        bench: [],
        rosterAthleteIds: [...starters, ...unused],
        strict: true,
      }).issues.map((item) => item.message);
    assert.ok(messages(["X1"]).includes("Tutti i calciatori in rosa devono essere schierati: manca 1 in panchina."));
    assert.ok(messages(["X1", "X2"]).includes("Tutti i calciatori in rosa devono essere schierati: mancano 2 in panchina."));
  });
});
