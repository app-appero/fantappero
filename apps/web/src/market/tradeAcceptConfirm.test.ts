import { describe, expect, it } from "vitest";
import {
  TRADE_ACCEPT_CANCEL_LABEL,
  TRADE_ACCEPT_CONFIRM_LABEL,
  TRADE_ACCEPT_CONFIRM_TITLE,
  tradeAcceptConfirmMessage,
} from "./tradeAcceptConfirm";

const BASE = {
  proposerTeamId: "team-a",
  recipientTeamId: "team-b",
  offeredAthletes: [],
  requestedAthletes: [],
  offeredCredits: 0,
  requestedCredits: 0,
};

const WARNING = "Lo scambio è immediato e non si può annullare.";

describe("tradeAcceptConfirmMessage", () => {
  it("titolo e pulsanti della conferma", () => {
    expect(TRADE_ACCEPT_CONFIRM_TITLE).toBe("Accettare lo scambio?");
    expect(TRADE_ACCEPT_CONFIRM_LABEL).toBe("Accetta scambio");
    expect(TRADE_ACCEPT_CANCEL_LABEL).toBe("Indietro");
  });

  it("il destinatario riceve gli offerti e cede i richiesti", () => {
    expect(
      tradeAcceptConfirmMessage(
        {
          ...BASE,
          offeredAthletes: [{ id: "a1", name: "Rossi" }],
          requestedAthletes: [{ id: "a2", name: "Verdi" }],
        },
        "team-b",
      ),
    ).toBe(`Riceverai Rossi e cederai Verdi. ${WARNING}`);
  });

  it("più calciatori separati da virgola e crediti come nella scheda", () => {
    expect(
      tradeAcceptConfirmMessage(
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
      ),
    ).toBe(`Riceverai Rossi, Bianchi + 10 crediti e cederai Verdi. ${WARNING}`);
  });

  it("crediti chiesti dal proponente: li cedi tu", () => {
    expect(
      tradeAcceptConfirmMessage(
        {
          ...BASE,
          offeredAthletes: [{ id: "a1", name: "Rossi" }],
          requestedAthletes: [{ id: "a2", name: "Verdi" }],
          requestedCredits: 1,
        },
        "team-b",
      ),
    ).toBe(`Riceverai Rossi e cederai Verdi + 1 credito. ${WARNING}`);
  });

  it("solo crediti da una parte", () => {
    expect(
      tradeAcceptConfirmMessage(
        { ...BASE, offeredCredits: 25, requestedAthletes: [{ id: "a2", name: "Verdi" }] },
        "team-b",
      ),
    ).toBe(`Riceverai 25 crediti e cederai Verdi. ${WARNING}`);
  });

  it("una parte vuota non lascia «cederai» o «riceverai» a metà", () => {
    expect(
      tradeAcceptConfirmMessage({ ...BASE, offeredAthletes: [{ id: "a1", name: "Rossi" }] }, "team-b"),
    ).toBe(`Riceverai Rossi senza cedere nulla. ${WARNING}`);
    expect(
      tradeAcceptConfirmMessage({ ...BASE, requestedAthletes: [{ id: "a2", name: "Verdi" }] }, "team-b"),
    ).toBe(`Cederai Verdi senza ricevere nulla. ${WARNING}`);
    expect(tradeAcceptConfirmMessage(BASE, "team-b")).toBe(WARNING);
  });

  it("dal punto di vista del proponente i lati si invertono", () => {
    expect(
      tradeAcceptConfirmMessage(
        {
          ...BASE,
          offeredAthletes: [{ id: "a1", name: "Rossi" }],
          requestedAthletes: [{ id: "a2", name: "Verdi" }],
          requestedCredits: 5,
        },
        "team-a",
      ),
    ).toBe(`Riceverai Verdi + 5 crediti e cederai Rossi. ${WARNING}`);
  });

  it("senza squadra nota vale il punto di vista del destinatario", () => {
    const proposal = {
      ...BASE,
      offeredAthletes: [{ id: "a1", name: "Rossi" }],
      requestedAthletes: [{ id: "a2", name: "Verdi" }],
    };
    expect(tradeAcceptConfirmMessage(proposal, undefined)).toBe(`Riceverai Rossi e cederai Verdi. ${WARNING}`);
    expect(tradeAcceptConfirmMessage(proposal, null)).toBe(`Riceverai Rossi e cederai Verdi. ${WARNING}`);
  });

  it("un nome mancante diventa «Giocatore»", () => {
    expect(
      tradeAcceptConfirmMessage(
        {
          ...BASE,
          offeredAthletes: [{ id: "a1", name: "  " }],
          requestedAthletes: [{ id: "a2", name: "Verdi" }],
        },
        "team-b",
      ),
    ).toBe(`Riceverai Giocatore e cederai Verdi. ${WARNING}`);
  });
});
