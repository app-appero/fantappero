import assert from "node:assert/strict";
import { describe, it } from "node:test";
import type { FantasyTeam } from "./leagues.ts";
import {
  approveTradeNotices,
  replacementConfirmNote,
  replacementPurchasedMessage,
  replacementUnaffordableNotice,
  rosterUnderQuotaNotice,
  teamUnderQuotaNotice,
  TRADE_SHORTFALL_COUNTER_LABEL,
  TRADE_SHORTFALL_COUNTER_TITLE,
  TRADE_SHORTFALL_PROPOSE_LABEL,
  TRADE_SHORTFALL_PROPOSE_TITLE,
  tradeAfterNotice,
  tradeAfterNoticeKey,
  tradeCreditsWarning,
  tradeProposeConfirmCopy,
  tradeQuotaNote,
  tradeShortfallWarning,
  underQuotaAfterPurchase,
  underQuotaAfterReplacements,
  underQuotaLabel,
  type TradeReplacementStatus,
  type TradeRosterAfter,
} from "./tradeReplacement.ts";

// Suggerimenti della corsa Mercato del 25/11: crediti che non bastano, testo della
// controproposta, ruoli sotto quota con la rosa piena. Solo avvisi: nessuna regola cambia.

const SHORT: TradeRosterAfter = {
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

/** 1 per 1 tra ruoli diversi: rosa alla misura, 10 Centrocampisti su 11. */
const FULL: TradeRosterAfter = {
  teamId: "t1",
  teamName: "Giulia United",
  sizeAfter: 35,
  rosterSize: 35,
  missingRoles: [],
  balanceAfter: 40,
  replacementCosts: [],
  canAffordReplacement: true,
  underQuotaRoles: [{ role: "C", count: 10, quota: 11 }],
};

function status(overrides: Partial<TradeReplacementStatus> = {}): TradeReplacementStatus {
  return {
    teamId: "t1",
    rosterSize: 35,
    filledSlots: 34,
    balance: 3,
    pending: [{ id: "r1", role: "D", tradeProposalId: "p1", createdAt: "2026-11-25T10:00:00Z" }],
    missingRoles: [{ role: "D", count: 1 }],
    tradeProposalId: "p1",
    otherTeamName: "Giulia United",
    receivedAthleteNames: ["N. Zortea"],
    receivedCredits: 0,
    blockedReason: null,
    blockedMessage: null,
    canAffordReplacement: false,
    cheapestReplacementPrice: 8,
    replacementCosts: [{ role: "D", count: 1, cheapestPrice: 8, totalPrice: 8 }],
    underQuotaRoles: [{ role: "D", count: 10, quota: 11 }],
    ...overrides,
  };
}

describe("crediti che non bastano per il sostituto", () => {
  it("prima dello scambio: il testo concordato, per chi accetta e per chi propone", () => {
    const text =
      "Attenzione: dopo lo scambio avrai 0 crediti e il Difensore libero più economico costa 8. " +
      "Da solo non potrai prendere il sostituto: dovrà assegnartelo l'admin.";
    assert.equal(tradeCreditsWarning(SHORT, "accept"), text);
    assert.equal(tradeCreditsWarning(SHORT, "propose"), text);
    assert.equal(
      tradeCreditsWarning({ ...SHORT, balanceAfter: 1 }, "accept"),
      "Attenzione: dopo lo scambio avrai 1 credito e il Difensore libero più economico costa 8. " +
        "Da solo non potrai prendere il sostituto: dovrà assegnartelo l'admin.",
    );
  });

  it("all'admin che approva: in terza persona, con il nome della squadra", () => {
    assert.equal(
      tradeCreditsWarning(SHORT, "approve"),
      "Attenzione: dopo lo scambio Giulia United avrà 0 crediti e il Difensore libero più economico " +
        "costa 8. Da sola non potrà prendere il sostituto: dovrà assegnarglielo l'admin.",
    );
  });

  it("il ruolo al singolare o al plurale giusto", () => {
    const forward: TradeRosterAfter = {
      ...SHORT,
      missingRoles: [{ role: "A", count: 1 }],
      replacementCosts: [{ role: "A", count: 1, cheapestPrice: 5, totalPrice: 5 }],
    };
    assert.match(tradeCreditsWarning(forward, "accept") ?? "", /e l'Attaccante libero più economico costa 5\./);
    const two: TradeRosterAfter = {
      ...SHORT,
      sizeAfter: 33,
      missingRoles: [{ role: "D", count: 2 }],
      replacementCosts: [{ role: "D", count: 2, cheapestPrice: 8, totalPrice: 17 }],
    };
    assert.equal(
      tradeCreditsWarning(two, "accept"),
      "Attenzione: dopo lo scambio avrai 0 crediti e i 2 Difensori liberi più economici costano 17 in " +
        "tutto. Da solo non potrai prendere i sostituti: dovrà assegnarteli l'admin.",
    );
    assert.match(tradeCreditsWarning(two, "approve") ?? "", /Da sola non potrà prendere i sostituti: dovrà assegnarglieli l'admin\.$/);
    const mixed: TradeRosterAfter = {
      ...SHORT,
      sizeAfter: 33,
      missingRoles: [
        { role: "C", count: 1 },
        { role: "D", count: 1 },
      ],
      replacementCosts: [
        { role: "C", count: 1, cheapestPrice: 4, totalPrice: 4 },
        { role: "D", count: 1, cheapestPrice: 8, totalPrice: 8 },
      ],
    };
    assert.match(
      tradeCreditsWarning(mixed, "accept") ?? "",
      /e il Difensore e il Centrocampista liberi più economici costano 12 in tutto\./,
    );
  });

  it("nessun avviso se i crediti bastano, se la rosa resta alla misura o con un server vecchio", () => {
    assert.equal(tradeCreditsWarning({ ...SHORT, canAffordReplacement: true, balanceAfter: 8 }, "accept"), null);
    assert.equal(tradeCreditsWarning(FULL, "accept"), null);
    assert.equal(tradeCreditsWarning(null, "accept"), null);
    const legacy: TradeRosterAfter = {
      teamId: "t1",
      teamName: "Giulia United",
      sizeAfter: 34,
      rosterSize: 35,
      missingRoles: [{ role: "D", count: 1 }],
    };
    assert.equal(tradeCreditsWarning(legacy, "accept"), null);
    // Nessun libero del ruolo: nessun prezzo da dire.
    assert.equal(
      tradeCreditsWarning(
        { ...SHORT, replacementCosts: [{ role: "D", count: 1, cheapestPrice: null, totalPrice: null }] },
        "accept",
      ),
      null,
    );
  });

  it("va sotto il testo arancione, che non cambia; lo scambio non si blocca", () => {
    const notice = tradeAfterNotice(SHORT, "accept");
    assert.equal(notice?.tone, "warning");
    assert.deepEqual(
      { title: notice?.title, body: notice?.body },
      tradeShortfallWarning(SHORT, "accept"),
    );
    assert.match(notice?.creditsWarning ?? "", /^Attenzione: dopo lo scambio avrai 0 crediti/);
    // D 10 su 11 è proprio il sostituto da scegliere: nessuna riga dei ruoli in più.
    assert.equal(notice?.quotaNote, null);
  });

  it("nella finestra: nessun libero alla portata", () => {
    assert.equal(
      replacementUnaffordableNotice(status(), "D"),
      "Nessun libero alla tua portata: hai 3 crediti e il più economico costa 8. Chiedi all'admin di " +
        "assegnarti un Difensore.",
    );
    assert.equal(
      replacementUnaffordableNotice(
        status({
          balance: 1,
          missingRoles: [{ role: "D", count: 2 }],
          replacementCosts: [{ role: "D", count: 2, cheapestPrice: 8, totalPrice: 16 }],
        }),
        "D",
      ),
      "Nessun libero alla tua portata: hai 1 credito e il più economico costa 8. Chiedi all'admin di " +
        "assegnarti 2 Difensori.",
    );
    assert.equal(replacementUnaffordableNotice(status({ balance: 8 }), "D"), null);
    // Server senza i prezzi per ruolo: vale il più economico in tutto.
    assert.match(
      replacementUnaffordableNotice(status({ replacementCosts: undefined }), "D") ?? "",
      /il più economico costa 8\./,
    );
    assert.equal(
      replacementUnaffordableNotice(status({ replacementCosts: undefined, cheapestReplacementPrice: undefined }), "D"),
      null,
    );
    assert.equal(replacementUnaffordableNotice(null, "D"), null);
  });
});

describe("testo della controproposta", () => {
  it("titolo e pulsante suoi; la proposta normale non cambia", () => {
    assert.equal(TRADE_SHORTFALL_COUNTER_TITLE, "Inviare la controproposta?");
    assert.equal(TRADE_SHORTFALL_COUNTER_LABEL, "Invia controproposta");
    assert.deepEqual(tradeProposeConfirmCopy("counter"), {
      title: "Inviare la controproposta?",
      label: "Invia controproposta",
    });
    assert.deepEqual(tradeProposeConfirmCopy("propose"), { title: "Proporre lo scambio?", label: "Proponi scambio" });
    assert.equal(TRADE_SHORTFALL_PROPOSE_TITLE, "Proporre lo scambio?");
    assert.equal(TRADE_SHORTFALL_PROPOSE_LABEL, "Proponi scambio");
  });
});

describe("ruoli sotto quota con la rosa piena", () => {
  it("numero, ruolo e quota con il plurale giusto", () => {
    assert.equal(underQuotaLabel([{ role: "C", count: 9, quota: 11 }]), "9 Centrocampisti su 11");
    assert.equal(underQuotaLabel([{ role: "P", count: 1, quota: 3 }]), "1 Portiere su 3");
    assert.equal(
      underQuotaLabel([
        { role: "C", count: 9, quota: 11 },
        { role: "P", count: 2, quota: 3 },
      ]),
      "2 Portieri su 3 e 9 Centrocampisti su 11",
    );
    // Solo i ruoli davvero sotto quota.
    assert.equal(underQuotaLabel([{ role: "D", count: 11, quota: 11 }]), "");
    assert.equal(underQuotaLabel(undefined), "");
  });

  it("prima dello scambio: riga informativa in un riquadro giallo se non mancano giocatori", () => {
    assert.equal(tradeQuotaNote(FULL, "accept"), "Dopo lo scambio avrai 10 Centrocampisti su 11.");
    assert.equal(tradeQuotaNote(FULL, "propose"), "Dopo lo scambio avrai 10 Centrocampisti su 11.");
    assert.equal(tradeQuotaNote(FULL, "approve"), "Dopo lo scambio Giulia United avrà 10 Centrocampisti su 11.");
    assert.deepEqual(tradeAfterNotice(FULL, "accept"), {
      tone: "info",
      title: null,
      body: null,
      creditsWarning: null,
      quotaNote: "Dopo lo scambio avrai 10 Centrocampisti su 11.",
    });
    assert.equal(tradeAfterNotice({ ...FULL, underQuotaRoles: [] }, "accept"), null);
  });

  it("nello stesso riquadro arancione se il ruolo resta sotto quota anche con il sostituto", () => {
    // Due C per un D: 34/35, il sostituto è un C, ma i C restano 10 su 11.
    const twoForOne: TradeRosterAfter = {
      ...SHORT,
      missingRoles: [{ role: "C", count: 1 }],
      balanceAfter: 50,
      replacementCosts: [{ role: "C", count: 1, cheapestPrice: 6, totalPrice: 6 }],
      canAffordReplacement: true,
      underQuotaRoles: [{ role: "C", count: 9, quota: 11 }],
    };
    assert.deepEqual(underQuotaAfterReplacements(twoForOne), [{ role: "C", count: 10, quota: 11 }]);
    const notice = tradeAfterNotice(twoForOne, "accept");
    assert.equal(notice?.tone, "warning");
    assert.equal(notice?.title, "Dopo lo scambio avrai 34/35");
    assert.equal(notice?.creditsWarning, null);
    assert.equal(notice?.quotaNote, "Anche con il sostituto avrai 10 Centrocampisti su 11.");
    assert.equal(
      tradeQuotaNote({ ...twoForOne, sizeAfter: 33, missingRoles: [{ role: "C", count: 2 }], underQuotaRoles: [{ role: "C", count: 8, quota: 11 }] }, "approve"),
      "Anche con i sostituti Giulia United avrà 10 Centrocampisti su 11.",
    );
    // Rosa corta per altri motivi (asta in corso): nessuna riga dei ruoli.
    assert.equal(tradeQuotaNote({ ...FULL, sizeAfter: 20 }, "accept"), null);
  });

  it("all'admin gli avvisi delle due squadre, con una chiave stabile", () => {
    const notices = approveTradeNotices({
      proposerTeamId: "t1",
      recipientTeamId: "t2",
      proposerRosterAfter: SHORT,
      recipientRosterAfter: { ...FULL, teamId: "t2", teamName: "Real Tiki" },
    });
    assert.equal(notices.length, 2);
    assert.equal(notices[0]?.title, "Dopo lo scambio Giulia United avrà 34/35");
    assert.match(notices[0]?.creditsWarning ?? "", /^Attenzione: dopo lo scambio Giulia United avrà 0 crediti/);
    assert.equal(notices[1]?.quotaNote, "Dopo lo scambio Real Tiki avrà 10 Centrocampisti su 11.");
    assert.equal(tradeAfterNoticeKey(notices[1]!), "Dopo lo scambio Real Tiki avrà 10 Centrocampisti su 11.");
    assert.deepEqual(approveTradeNotices({ proposerTeamId: "t1", recipientTeamId: "t2" }), []);
  });

  it("in Rosa: riquadro informativo solo con la rosa alla misura", () => {
    const text = "Ruoli sotto quota: 9 Centrocampisti su 11. Puoi completarli con uno scambio o agli svincolati.";
    assert.equal(
      rosterUnderQuotaNotice({ filledSlots: 35, rosterSize: 35, underQuotaRoles: [{ role: "C", count: 9, quota: 11 }] }),
      text,
    );
    assert.equal(
      rosterUnderQuotaNotice({ filledSlots: 34, rosterSize: 35, underQuotaRoles: [{ role: "C", count: 9, quota: 11 }] }),
      null,
    );
    assert.equal(rosterUnderQuotaNotice({ filledSlots: 35, rosterSize: 35, underQuotaRoles: [] }), null);
    assert.equal(rosterUnderQuotaNotice({ filledSlots: 35, rosterSize: 35 }), null);
    const team = {
      filledSlots: 35,
      rosterSize: 35,
      composition: {
        status: "validated",
        filledSlots: 35,
        competitionCount: 3,
        requireComplete: true,
        validatedAt: null,
        limits: { rosterSize: 35, goalkeepers: 3, defenders: 11, midfielders: 11, forwards: 10 },
        counts: { P: 3, D: 12, C: 9, A: 11 },
        issues: [],
        underQuotaRoles: [{ role: "C" as const, count: 9, quota: 11 }],
      },
    } satisfies Pick<FantasyTeam, "filledSlots" | "rosterSize" | "composition">;
    assert.equal(teamUnderQuotaNotice(team), text);
    assert.equal(teamUnderQuotaNotice({ ...team, composition: null }), null);
    assert.equal(teamUnderQuotaNotice(null), null);
  });

  it("fine della finestra: se dopo l'ultimo sostituto resta un ruolo sotto quota lo dice", () => {
    const last = status({ balance: 50, underQuotaRoles: [{ role: "C", count: 10, quota: 11 }, { role: "D", count: 10, quota: 11 }] });
    assert.deepEqual(underQuotaAfterPurchase(last.underQuotaRoles, "D"), [{ role: "C", count: 10, quota: 11 }]);
    assert.equal(
      replacementConfirmNote(last, "D"),
      "La rosa torna 35/35 e puoi schierare subito la formazione. Vale anche a mercato chiuso. " +
        "Ruoli sotto quota: 10 Centrocampisti su 11. Puoi completarli con uno scambio o agli svincolati.",
    );
    // Il sostituto riporta il ruolo alla quota: il testo di sempre.
    assert.equal(
      replacementConfirmNote(status({ underQuotaRoles: [{ role: "D", count: 10, quota: 11 }] }), "D"),
      "La rosa torna 35/35 e puoi schierare subito la formazione. Vale anche a mercato chiuso.",
    );
    assert.equal(
      replacementPurchasedMessage({
        athleteName: "N. Rossi",
        priceCredits: 6,
        status: status({ filledSlots: 35, pending: [], missingRoles: [], underQuotaRoles: [{ role: "C", count: 10, quota: 11 }] }),
      }),
      "Hai preso N. Rossi per 6 crediti. La rosa è completa: puoi schierare la formazione. " +
        "Ruoli sotto quota: 10 Centrocampisti su 11. Puoi completarli con uno scambio o agli svincolati.",
    );
    assert.equal(
      replacementPurchasedMessage({
        athleteName: "N. Rossi",
        priceCredits: 6,
        status: status({ filledSlots: 35, pending: [], missingRoles: [], underQuotaRoles: [] }),
      }),
      "Hai preso N. Rossi per 6 crediti. La rosa è completa: puoi schierare la formazione.",
    );
  });
});
