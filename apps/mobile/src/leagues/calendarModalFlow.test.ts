import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
  calendarButtonsDisabled,
  calendarModalAfterCheck,
  calendarModalAfterError,
  calendarModalChecking,
  calendarProceedForce,
  participantsShortcutTab,
} from "./calendarModalFlow.ts";

const TEAM = {
  teamId: "team-x",
  teamName: "Squadra X",
  issues: ["Difensori 10 su 11"],
  lineupBlocked: false,
};

describe("finestra «Genera/Conferma calendario» nell'app (1.5)", () => {
  it("si apre sul controllo delle rose", () => {
    assert.deepEqual(calendarModalChecking("generate"), {
      action: "generate",
      phase: "checking",
      teams: [],
    });
  });

  it("dopo il controllo: rose in regola = conferma normale, rose da sistemare = avviso", () => {
    const checking = calendarModalChecking("generate");
    const ok = calendarModalAfterCheck(checking, "generate", []);
    assert.deepEqual(ok, { action: "generate", phase: "ready", teams: [] });
    assert.equal(calendarProceedForce(ok), false);

    const warning = calendarModalAfterCheck(checking, "generate", [TEAM]);
    assert.deepEqual(warning?.teams, [TEAM]);
    assert.equal(calendarProceedForce(warning), true);
  });

  it("la risposta del controllo arrivata a finestra chiusa o cambiata si ignora", () => {
    assert.equal(calendarModalAfterCheck(null, "generate", [TEAM]), null);
    const confirmOpen = calendarModalChecking("confirm");
    assert.equal(calendarModalAfterCheck(confirmOpen, "generate", [TEAM]), confirmOpen);
  });

  it("durante la verifica «comunque» non vale", () => {
    assert.equal(calendarProceedForce(calendarModalChecking("confirm")), false);
    assert.equal(calendarProceedForce(null), false);
  });

  it("errore league_rosters_invalid: la finestra passa all'avviso, con «comunque»", () => {
    const state = calendarModalAfterError("confirm", [TEAM]);
    assert.deepEqual(state, { action: "confirm", phase: "ready", teams: [TEAM] });
    assert.equal(calendarProceedForce(state), true);
  });

  it("ogni altro errore chiude la finestra e lascia l'errore al pannello", () => {
    assert.equal(calendarModalAfterError("generate", null), null);
    assert.equal(calendarModalAfterError("generate", []), null);
  });

  it("Genera e Conferma si bloccano con l'azione in corso o la finestra aperta", () => {
    assert.equal(calendarButtonsDisabled({ working: false, modalOpen: false }), false);
    assert.equal(calendarButtonsDisabled({ working: true, modalOpen: false }), true);
    assert.equal(calendarButtonsDisabled({ working: false, modalOpen: true }), true);
  });

  it("«Vai a Partecipanti» apre «Invitati» solo a configurazione salvata (QA 28/11, D2)", () => {
    assert.equal(participantsShortcutTab(true), "invitati");
    // Configurazione mai salvata: «Invitati» è disattivata, si va a «Configurazione».
    assert.equal(participantsShortcutTab(false), "configurazione");
  });
});
