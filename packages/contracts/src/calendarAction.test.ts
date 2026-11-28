import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
  CALENDAR_ACTION_COPY,
  calendarBlockedNote,
  calendarErrorNeedsParticipants,
  calendarForceNote,
  calendarGeneratedMessage,
  calendarIssueText,
  calendarProceedLabel,
  calendarRosterIssuesFromPayload,
  joinTeamNames,
} from "./calendarAction.ts";

const TEAM = {
  teamId: "team-x",
  teamName: "Squadra X",
  issues: ["Difensori 10 su 11", "Attaccanti 11 su 10"],
  lineupBlocked: false,
};

describe("«Genera/Conferma calendario» con controllo delle rose (Rosario 22/11, 1.5 app)", () => {
  it("domanda e pulsanti sono quelli del sito", () => {
    assert.equal(CALENDAR_ACTION_COPY.generate.title, "Genera calendario");
    assert.match(CALENDAR_ACTION_COPY.generate.prompt, /^Vuoi generare il calendario\?/);
    assert.match(CALENDAR_ACTION_COPY.confirm.prompt, /^Vuoi confermare il calendario\?/);
    assert.equal(calendarProceedLabel("generate", false, false), "Genera calendario");
    assert.equal(calendarProceedLabel("generate", true, false), "Genera comunque");
    assert.equal(calendarProceedLabel("confirm", false, false), "Conferma calendario");
    assert.equal(calendarProceedLabel("confirm", true, false), "Conferma comunque");
    assert.equal(calendarProceedLabel("generate", true, true), "Generazione…");
    assert.equal(calendarProceedLabel("confirm", false, true), "Conferma…");
  });

  it("avviso con rose non in regola: squadre e problemi, esuberi non schierabili", () => {
    assert.equal(calendarIssueText(TEAM), "Squadra X: Difensori 10 su 11, Attaccanti 11 su 10");
    assert.match(calendarForceNote("generate"), /^Puoi generare comunque il calendario/);
    assert.match(calendarForceNote("confirm"), /^Puoi confermare comunque il calendario/);
    assert.match(
      calendarForceNote("generate"),
      /i calciatori in esubero restano in rosa ma non potranno essere schierati/,
    );
  });

  it("le squadre che non schierano proprio la formazione si nominano a parte", () => {
    assert.equal(calendarBlockedNote([TEAM]), null);
    const blocked = { ...TEAM, teamName: "Squadra Y", lineupBlocked: true };
    assert.equal(
      calendarBlockedNote([TEAM, blocked]),
      "Squadra Y invece non potrà schierare la formazione finché la rosa non sarà completa e con almeno 3 campionati.",
    );
    const other = { ...blocked, teamName: "Squadra Z" };
    assert.match(calendarBlockedNote([blocked, other]) ?? "", /^Squadra Y e Squadra Z invece non potranno schierare/);
    assert.equal(joinTeamNames(["A", "B", "C"]), "A, B e C");
    assert.equal(joinTeamNames(["A"]), "A");
    assert.equal(joinTeamNames([]), "");
  });

  it("legge le squadre dal corpo dell'errore league_rosters_invalid", () => {
    assert.deepEqual(
      calendarRosterIssuesFromPayload({
        teams: [
          { teamId: "t1", teamName: "Squadra X", issues: ["Portieri 2 su 3", 4], lineupBlocked: true },
          { teamName: "Senza id", issues: "no" },
          { issues: [] },
          null,
        ],
      }),
      [
        { teamId: "t1", teamName: "Squadra X", issues: ["Portieri 2 su 3"], lineupBlocked: true },
        { teamId: null, teamName: "Senza id", issues: [], lineupBlocked: false },
      ],
    );
    assert.deepEqual(calendarRosterIssuesFromPayload({}), []);
    assert.deepEqual(calendarRosterIssuesFromPayload(undefined), []);
  });

  it("esiti e «Vai a Partecipanti»", () => {
    assert.equal(
      calendarGeneratedMessage({ matchupCount: 6, roundCount: 3 }),
      "Calendario generato: 6 incontri su 3 giornate.",
    );
    assert.equal(calendarErrorNeedsParticipants("Completa le rose di tutti i partecipanti."), true);
    assert.equal(calendarErrorNeedsParticipants("Servono più Partecipanti."), true);
    assert.equal(calendarErrorNeedsParticipants("Errore di rete."), false);
    assert.equal(calendarErrorNeedsParticipants(null), false);
  });
});
