import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
  canAssignRandomRoster,
  canManageMember,
  canOpenMemberProfile,
  memberRemovedMessage,
  memberRoleLabel,
  randomRosterAssignedMessage,
} from "./memberRow.ts";

describe("partecipanti in Amministrazione lega: profilo e rosa random (1.5)", () => {
  it("il ruolo dice anche se è un fantallenatore IA", () => {
    assert.equal(memberRoleLabel({ role: "league_admin", userType: "human" }), "Amministratore");
    assert.equal(memberRoleLabel({ role: "member", userType: "human" }), "Partecipante");
    assert.equal(memberRoleLabel({ role: "member", userType: "ai" }), "Partecipante · IA");
  });

  it("il profilo si apre per tutti tranne che per sé", () => {
    assert.equal(canOpenMemberProfile({ userId: "u1" }, "u2"), true);
    assert.equal(canOpenMemberProfile({ userId: "u1" }, "u1"), false);
    assert.equal(canOpenMemberProfile({ userId: "u1" }, null), true);
  });

  it("«Rimuovi» solo per i partecipanti, solo prima dell'avvio", () => {
    assert.equal(canManageMember({ role: "member" }, true), true);
    assert.equal(canManageMember({ role: "member" }, false), false);
    assert.equal(canManageMember({ role: "league_admin" }, true), false);
  });

  it("«Assegna rosa random» solo per le IA", () => {
    assert.equal(canAssignRandomRoster({ role: "member", userType: "ai" }, true), true);
    assert.equal(canAssignRandomRoster({ role: "member", userType: "human" }, true), false);
    assert.equal(canAssignRandomRoster({ role: "member", userType: "ai" }, false), false);
    assert.equal(canAssignRandomRoster({ role: "league_admin", userType: "ai" }, true), false);
  });

  it("messaggi di esito", () => {
    assert.equal(
      randomRosterAssignedMessage("Allenatore IA 01", { filledSlots: 25, rosterSize: 25 }),
      "Rosa random assegnata a Allenatore IA 01: 25/25 giocatori.",
    );
    assert.equal(
      memberRemovedMessage("Giulia"),
      "Giulia è stato rimosso dalla lega. Il numero partecipanti previsti è stato allineato agli iscritti.",
    );
  });
});
