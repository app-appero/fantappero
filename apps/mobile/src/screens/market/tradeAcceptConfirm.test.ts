import assert from "node:assert/strict";
import test from "node:test";
import {
  TRADE_ACCEPT_CANCEL_LABEL,
  TRADE_ACCEPT_CONFIRM_LABEL,
  TRADE_ACCEPT_CONFIRM_TITLE,
  tradeAcceptConfirmMessage,
} from "./tradeAcceptConfirm.ts";

const BASE = {
  proposerTeamId: "team-a",
  recipientTeamId: "team-b",
  offeredAthletes: [],
  requestedAthletes: [],
  offeredCredits: 0,
  requestedCredits: 0,
};

const WARNING = "Lo scambio è immediato e non si può annullare.";

test("titolo e pulsanti della conferma", () => {
  assert.equal(TRADE_ACCEPT_CONFIRM_TITLE, "Accettare lo scambio?");
  assert.equal(TRADE_ACCEPT_CONFIRM_LABEL, "Accetta scambio");
  assert.equal(TRADE_ACCEPT_CANCEL_LABEL, "Indietro");
});

test("il destinatario riceve gli offerti e cede i richiesti", () => {
  const message = tradeAcceptConfirmMessage(
    {
      ...BASE,
      offeredAthletes: [{ id: "a1", name: "Rossi" }],
      requestedAthletes: [{ id: "a2", name: "Verdi" }],
    },
    "team-b",
  );
  assert.equal(message, `Riceverai Rossi e cederai Verdi. ${WARNING}`);
});

test("più calciatori separati da virgola e crediti come nella scheda", () => {
  const message = tradeAcceptConfirmMessage(
    {
      ...BASE,
      offeredAthletes: [
        { id: "a1", name: "Rossi" },
        { id: "a3", name: "Bianchi" },
      ],
      offeredCredits: 10,
      requestedAthletes: [{ id: "a2", name: "Verdi" }],
    },
    "team-b",
  );
  assert.equal(message, `Riceverai Rossi, Bianchi + 10 crediti e cederai Verdi. ${WARNING}`);
});

test("crediti chiesti dal proponente: li cedi tu", () => {
  const message = tradeAcceptConfirmMessage(
    {
      ...BASE,
      offeredAthletes: [{ id: "a1", name: "Rossi" }],
      requestedAthletes: [{ id: "a2", name: "Verdi" }],
      requestedCredits: 1,
    },
    "team-b",
  );
  assert.equal(message, `Riceverai Rossi e cederai Verdi + 1 credito. ${WARNING}`);
});

test("solo crediti da una parte", () => {
  const message = tradeAcceptConfirmMessage(
    { ...BASE, offeredCredits: 25, requestedAthletes: [{ id: "a2", name: "Verdi" }] },
    "team-b",
  );
  assert.equal(message, `Riceverai 25 crediti e cederai Verdi. ${WARNING}`);
});

test("una parte vuota non lascia «cederai» o «riceverai» a metà", () => {
  assert.equal(
    tradeAcceptConfirmMessage({ ...BASE, offeredAthletes: [{ id: "a1", name: "Rossi" }] }, "team-b"),
    `Riceverai Rossi senza cedere nulla. ${WARNING}`,
  );
  assert.equal(
    tradeAcceptConfirmMessage({ ...BASE, requestedAthletes: [{ id: "a2", name: "Verdi" }] }, "team-b"),
    `Cederai Verdi senza ricevere nulla. ${WARNING}`,
  );
  assert.equal(tradeAcceptConfirmMessage(BASE, "team-b"), WARNING);
});

test("dal punto di vista del proponente i lati si invertono", () => {
  const message = tradeAcceptConfirmMessage(
    {
      ...BASE,
      offeredAthletes: [{ id: "a1", name: "Rossi" }],
      requestedAthletes: [{ id: "a2", name: "Verdi" }],
      requestedCredits: 5,
    },
    "team-a",
  );
  assert.equal(message, `Riceverai Verdi + 5 crediti e cederai Rossi. ${WARNING}`);
});

test("senza squadra nota vale il punto di vista del destinatario", () => {
  const proposal = {
    ...BASE,
    offeredAthletes: [{ id: "a1", name: "Rossi" }],
    requestedAthletes: [{ id: "a2", name: "Verdi" }],
  };
  assert.equal(tradeAcceptConfirmMessage(proposal, undefined), `Riceverai Rossi e cederai Verdi. ${WARNING}`);
  assert.equal(tradeAcceptConfirmMessage(proposal, null), `Riceverai Rossi e cederai Verdi. ${WARNING}`);
});

test("un nome mancante diventa «Giocatore»", () => {
  const message = tradeAcceptConfirmMessage(
    {
      ...BASE,
      offeredAthletes: [{ id: "a1", name: "  " }],
      requestedAthletes: [{ id: "a2", name: "Verdi" }],
    },
    "team-b",
  );
  assert.equal(message, `Riceverai Giocatore e cederai Verdi. ${WARNING}`);
});
