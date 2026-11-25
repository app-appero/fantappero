import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
  creditsAfterReplacement,
  missingAfterPurchase,
  missingRolesLabel,
  missingRolesTotal,
  myRosterAfter,
  replacementBanner,
  replacementChips,
  replacementConfirmNote,
  replacementConfirmTitle,
  replacementCreditRows,
  replacementDoneBanner,
  replacementIntro,
  replacementPromptStorageKey,
  replacementPurchasedMessage,
  replacementRoles,
  replacementTakeLabel,
  roleCountLabel,
  shortRostersAfter,
  shouldAutoOpenReplacement,
  tradeShortfallWarning,
  type TradeReplacementStatus,
  type TradeRosterAfter,
} from "./tradeReplacement.ts";

const SHORT: TradeRosterAfter = {
  teamId: "t1",
  teamName: "Giulia United",
  sizeAfter: 34,
  rosterSize: 35,
  missingRoles: [{ role: "D", count: 1 }],
};

function status(overrides: Partial<TradeReplacementStatus> = {}): TradeReplacementStatus {
  return {
    teamId: "t1",
    rosterSize: 35,
    filledSlots: 34,
    balance: 120,
    pending: [{ id: "r1", role: "D", tradeProposalId: "p1", createdAt: "2026-11-25T10:00:00Z" }],
    missingRoles: [{ role: "D", count: 1 }],
    tradeProposalId: "p1",
    otherTeamName: "Giulia United",
    receivedAthleteNames: ["N. Zortea"],
    receivedCredits: 0,
    blockedReason: null,
    blockedMessage: null,
    ...overrides,
  };
}

describe("sostituto dopo lo scambio: ruoli e plurali (1.5)", () => {
  it("dice numero e ruolo con il plurale giusto", () => {
    assert.equal(roleCountLabel("D", 1), "1 Difensore");
    assert.equal(roleCountLabel("D", 2), "2 Difensori");
    assert.equal(roleCountLabel("A", 2), "2 Attaccanti");
    assert.equal(missingRolesLabel([{ role: "D", count: 2 }]), "2 Difensori");
    assert.equal(
      missingRolesLabel([
        { role: "C", count: 1 },
        { role: "D", count: 1 },
      ]),
      "1 Difensore e 1 Centrocampista",
    );
    assert.equal(
      missingRolesLabel([
        { role: "A", count: 1 },
        { role: "P", count: 1 },
        { role: "D", count: 2 },
      ]),
      "1 Portiere, 2 Difensori e 1 Attaccante",
    );
    assert.equal(missingRolesLabel([]), "");
    assert.equal(missingRolesTotal([{ role: "D", count: 2 }, { role: "C", count: 1 }]), 3);
    assert.deepEqual(replacementRoles([{ role: "C", count: 1 }, { role: "D", count: 1 }]), ["D", "C"]);
  });
});

describe("avviso prima dello scambio", () => {
  it("chi accetta legge il testo concordato", () => {
    assert.deepEqual(tradeShortfallWarning(SHORT, "accept"), {
      title: "Dopo lo scambio avrai 34/35",
      body:
        "Ti mancherà un Difensore. Appena accetti dovrai sceglierlo dagli svincolati, al suo Valore. " +
        "Finché non lo scegli non potrai schierare la formazione.",
    });
  });

  it("al plurale e con più ruoli", () => {
    const two = tradeShortfallWarning({ ...SHORT, sizeAfter: 33, missingRoles: [{ role: "D", count: 2 }] }, "accept");
    assert.equal(two?.title, "Dopo lo scambio avrai 33/35");
    assert.equal(
      two?.body,
      "Ti mancheranno 2 Difensori. Appena accetti dovrai sceglierli dagli svincolati, al loro Valore. " +
        "Finché non li scegli non potrai schierare la formazione.",
    );
    const mixed = tradeShortfallWarning(
      {
        ...SHORT,
        sizeAfter: 33,
        missingRoles: [
          { role: "D", count: 1 },
          { role: "C", count: 1 },
        ],
      },
      "accept",
    );
    assert.match(mixed?.body ?? "", /^Ti mancheranno 1 Difensore e 1 Centrocampista\./);
  });

  it("chi propone e l'amministratore che approva", () => {
    assert.equal(
      tradeShortfallWarning(SHORT, "propose")?.body,
      "Ti mancherà un Difensore. Se lo scambio viene accettato dovrai sceglierlo dagli svincolati, al suo " +
        "Valore. Finché non lo scegli non potrai schierare la formazione.",
    );
    assert.deepEqual(tradeShortfallWarning(SHORT, "approve"), {
      title: "Dopo lo scambio Giulia United avrà 34/35",
      body:
        "Le mancherà un Difensore. Appena approvi dovrà sceglierlo dagli svincolati, al suo Valore. " +
        "Finché non lo sceglie non potrà schierare la formazione.",
    });
  });

  it("nessun avviso senza sostituti da scegliere", () => {
    assert.equal(tradeShortfallWarning(null, "accept"), null);
    assert.equal(tradeShortfallWarning({ ...SHORT, sizeAfter: 36, missingRoles: [] }, "accept"), null);
  });

  it("trova la rosa della mia squadra e quelle corte per l'admin", () => {
    const proposal = {
      proposerTeamId: "t1",
      recipientTeamId: "t2",
      proposerRosterAfter: SHORT,
      recipientRosterAfter: { ...SHORT, teamId: "t2", sizeAfter: 36, missingRoles: [] },
    };
    assert.equal(myRosterAfter(proposal, "t1"), SHORT);
    assert.equal(myRosterAfter(proposal, "t2")?.sizeAfter, 36);
    assert.equal(myRosterAfter(proposal, "t3"), null);
    assert.equal(myRosterAfter({ proposerTeamId: "t1", recipientTeamId: "t2" }, "t1"), null);
    assert.deepEqual(shortRostersAfter(proposal), [SHORT]);
  });
});

describe("finestra «Scegli il sostituto»", () => {
  it("riquadro verde, testo ed etichette", () => {
    assert.equal(replacementDoneBanner(status()), "Scambio fatto: è arrivato N. Zortea");
    assert.equal(
      replacementDoneBanner(status({ receivedAthleteNames: ["A. Uno", "B. Due"] })),
      "Scambio fatto: sono arrivati A. Uno e B. Due",
    );
    assert.equal(
      replacementDoneBanner(status({ receivedAthleteNames: [], receivedCredits: 30 })),
      "Scambio fatto: hai ricevuto 30 crediti",
    );
    assert.equal(replacementDoneBanner(status({ tradeProposalId: null })), null);
    assert.equal(replacementIntro(status().missingRoles), "Ti manca 1 Difensore. Scegline uno tra i liberi: lo paghi il suo Valore.");
    assert.equal(
      replacementIntro([{ role: "D", count: 2 }]),
      "Ti mancano 2 Difensori. Scegline uno alla volta tra i liberi: lo paghi il suo Valore.",
    );
    assert.deepEqual(replacementChips(status(), "D"), ["Rosa 34/35", "Crediti 120", "Solo D"]);
    assert.equal(replacementTakeLabel(12), "Prendi · 12");
  });

  it("conferma con il conto dei crediti", () => {
    assert.equal(replacementConfirmTitle("N. Rossi", 12), "Prendi N. Rossi per 12 crediti?");
    assert.equal(replacementConfirmTitle("N. Rossi", 1), "Prendi N. Rossi per 1 credito?");
    assert.deepEqual(replacementCreditRows(120, "N. Rossi", 12), [
      { label: "Crediti ora", value: "120" },
      { label: "Valore di N. Rossi", value: "− 12" },
      { label: "Ti restano", value: "108", total: true },
    ]);
    assert.equal(creditsAfterReplacement(120, 12), 108);
    assert.equal(
      replacementConfirmNote(status(), "D"),
      "La rosa torna 35/35 e puoi schierare subito la formazione. Vale anche a mercato chiuso.",
    );
  });

  it("con due da scegliere si sceglie uno alla volta", () => {
    const two = status({ filledSlots: 33, missingRoles: [{ role: "D", count: 2 }] });
    assert.deepEqual(missingAfterPurchase(two.missingRoles, "D"), [{ role: "D", count: 1 }]);
    assert.equal(
      replacementConfirmNote(two, "D"),
      "La rosa sale a 34/35: poi ti resta da scegliere 1 Difensore. Vale anche a mercato chiuso.",
    );
    assert.equal(
      replacementPurchasedMessage({ athleteName: "N. Rossi", priceCredits: 12, status: { ...two, missingRoles: [{ role: "D", count: 1 }] } }),
      "Hai preso N. Rossi per 12 crediti. Ti resta da scegliere 1 Difensore.",
    );
    assert.equal(
      replacementPurchasedMessage({ athleteName: "N. Rossi", priceCredits: 1, status: status({ pending: [], missingRoles: [] }) }),
      "Hai preso N. Rossi per 1 credito. La rosa è completa: puoi schierare la formazione.",
    );
  });
});

describe("riquadro in Rosa e Formazione e apertura automatica", () => {
  it("dice cosa manca e apre la scelta", () => {
    assert.deepEqual(replacementBanner(status()), {
      title: "Rosa incompleta: 34/35",
      body: "Ti manca un Difensore dopo lo scambio. Sceglilo per poter schierare la formazione.",
      action: "Scegli il sostituto (Difensore)",
      blockedMessage: null,
    });
    const two = replacementBanner(
      status({
        filledSlots: 33,
        missingRoles: [{ role: "D", count: 2 }],
        blockedMessage: "Il turno 12 è in corso…",
      }),
    );
    assert.equal(two?.body, "Ti mancano 2 Difensori dopo lo scambio. Sceglili per poter schierare la formazione.");
    assert.equal(two?.blockedMessage, "Il turno 12 è in corso…");
    assert.equal(replacementBanner(status({ pending: [], missingRoles: [] })), null);
    assert.equal(replacementBanner(null), null);
  });

  it("una volta per sessione", () => {
    assert.equal(replacementPromptStorageKey("lega-1"), "fa.sostituto.rimandato.lega-1");
    assert.equal(shouldAutoOpenReplacement(status(), false), true);
    assert.equal(shouldAutoOpenReplacement(status(), true), false);
    assert.equal(shouldAutoOpenReplacement(status({ pending: [] }), false), false);
    assert.equal(shouldAutoOpenReplacement(null, false), false);
  });
});
