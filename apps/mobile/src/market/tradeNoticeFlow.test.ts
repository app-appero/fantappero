import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
  approveTradeNotices,
  replacementUnaffordableNotice,
  teamUnderQuotaNotice,
  tradeAfterNotice,
  tradeProposeConfirmCopy,
  type TradeRosterAfter,
} from "../../../../packages/contracts/src/tradeReplacement.ts";
import { tradeAcceptConfirmMode, tradeCreditsSplit, tradePreviewDraft } from "./tradeNoticeFlow.ts";

// Corsa Mercato del 25/11 nell'app: crediti che non bastano per il sostituto, testo della
// controproposta, ruoli sotto quota con la rosa piena. Stesse scelte del sito.

const SHORT_POOR: TradeRosterAfter = {
  teamId: "t1",
  teamName: "Giulia United",
  sizeAfter: 34,
  rosterSize: 35,
  missingRoles: [{ role: "D", count: 1 }],
  balanceAfter: 0,
  replacementCosts: [{ role: "D", count: 1, cheapestPrice: 8, totalPrice: 8 }],
  canAffordReplacement: false,
  underQuotaRoles: [{ role: "D", count: 10, quota: 11 }],
};

const FULL_UNDER_QUOTA: TradeRosterAfter = {
  teamId: "t1",
  teamName: "Giulia United",
  sizeAfter: 35,
  rosterSize: 35,
  missingRoles: [],
  underQuotaRoles: [{ role: "C", count: 9, quota: 11 }],
};

describe("anteprima prima di proporre o controproporre", () => {
  it("manda i crediti offerti o chiesti, per i crediti dopo lo scambio", () => {
    assert.deepEqual(tradeCreditsSplit("offer", "12"), { offeredCredits: 12, requestedCredits: 0 });
    assert.deepEqual(tradeCreditsSplit("request", 7), { offeredCredits: 0, requestedCredits: 7 });
    assert.deepEqual(tradeCreditsSplit("offer", ""), { offeredCredits: 0, requestedCredits: 0 });
    assert.deepEqual(tradeCreditsSplit("offer", "-3"), { offeredCredits: 0, requestedCredits: 0 });
    assert.deepEqual(
      tradePreviewDraft({
        recipientTeamId: "t2",
        offeredAthleteIds: ["a1"],
        requestedAthleteIds: ["b1"],
        direction: "offer",
        amount: "5",
      }),
      { recipientTeamId: "t2", offeredAthleteIds: ["a1"], requestedAthleteIds: ["b1"], offeredCredits: 5, requestedCredits: 0 },
    );
  });

  it("anche per un 1 per 1 (ruoli sotto quota), non senza calciatori o senza destinatario", () => {
    assert.notEqual(
      tradePreviewDraft({ recipientTeamId: "t2", offeredAthleteIds: ["a1"], requestedAthleteIds: ["b1"], direction: "offer", amount: 0 }),
      null,
    );
    assert.equal(
      tradePreviewDraft({ recipientTeamId: "t2", offeredAthleteIds: [], requestedAthleteIds: [], direction: "offer", amount: 30 }),
      null,
    );
    assert.equal(
      tradePreviewDraft({ recipientTeamId: undefined, offeredAthleteIds: ["a1"], requestedAthleteIds: [], direction: "offer", amount: 0 }),
      null,
    );
  });
});

describe("conferma di «Accetta»", () => {
  it("rosa corta senza crediti: foglio con «Accetta e scegli» e l'avviso dei crediti", () => {
    const notice = tradeAfterNotice(SHORT_POOR, "accept");
    assert.equal(tradeAcceptConfirmMode(notice), "short");
    assert.equal(
      notice?.creditsWarning,
      "Attenzione: dopo lo scambio avrai 0 crediti e il Difensore libero più economico costa 8. " +
        "Da solo non potrai prendere il sostituto: dovrà assegnartelo l'admin.",
    );
  });

  it("solo un ruolo sotto quota: foglio con il riquadro giallo e il pulsante di sempre", () => {
    const notice = tradeAfterNotice(FULL_UNDER_QUOTA, "accept");
    assert.equal(tradeAcceptConfirmMode(notice), "info");
    assert.equal(notice?.quotaNote, "Dopo lo scambio avrai 9 Centrocampisti su 11.");
  });

  it("niente da dire: la finestra di sistema di sempre", () => {
    assert.equal(tradeAcceptConfirmMode(tradeAfterNotice({ ...FULL_UNDER_QUOTA, underQuotaRoles: [] }, "accept")), "alert");
    assert.equal(tradeAcceptConfirmMode(null), "alert");
  });
});

describe("controproposta e admin", () => {
  it("la controproposta ha titolo e pulsante suoi", () => {
    assert.deepEqual(tradeProposeConfirmCopy("counter"), {
      title: "Inviare la controproposta?",
      label: "Invia controproposta",
    });
    assert.deepEqual(tradeProposeConfirmCopy("propose"), { title: "Proporre lo scambio?", label: "Proponi scambio" });
  });

  it("l'admin vede le due squadre, in terza persona", () => {
    const notices = approveTradeNotices({
      proposerTeamId: "t1",
      recipientTeamId: "t2",
      proposerRosterAfter: SHORT_POOR,
      recipientRosterAfter: { ...FULL_UNDER_QUOTA, teamId: "t2", teamName: "Real Tiki" },
    });
    assert.equal(notices.length, 2);
    assert.match(notices[0]?.creditsWarning ?? "", /Giulia United avrà 0 crediti/);
    assert.equal(notices[1]?.quotaNote, "Dopo lo scambio Real Tiki avrà 9 Centrocampisti su 11.");
  });
});

describe("foglio dei sostituti e Rosa", () => {
  it("nessun libero alla portata", () => {
    assert.equal(
      replacementUnaffordableNotice(
        {
          balance: 0,
          missingRoles: [{ role: "D", count: 1 }],
          replacementCosts: [{ role: "D", count: 1, cheapestPrice: 8, totalPrice: 8 }],
        },
        "D",
      ),
      "Nessun libero alla tua portata: hai 0 crediti e il più economico costa 8. Chiedi all'admin di assegnarti un Difensore.",
    );
  });

  it("riquadro «Ruoli sotto quota» in Rosa con la rosa alla misura", () => {
    const composition = {
      status: "validated",
      filledSlots: 35,
      competitionCount: 3,
      requireComplete: true,
      validatedAt: null,
      limits: { rosterSize: 35, goalkeepers: 3, defenders: 11, midfielders: 11, forwards: 10 },
      counts: { P: 3, D: 12, C: 9, A: 11 },
      issues: [],
      underQuotaRoles: [{ role: "C" as const, count: 9, quota: 11 }],
    };
    assert.equal(
      teamUnderQuotaNotice({ filledSlots: 35, rosterSize: 35, composition }),
      "Ruoli sotto quota: 9 Centrocampisti su 11. Puoi completarli con uno scambio o agli svincolati.",
    );
    assert.equal(teamUnderQuotaNotice({ filledSlots: 34, rosterSize: 35, composition }), null);
  });
});
