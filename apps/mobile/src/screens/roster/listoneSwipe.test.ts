import assert from "node:assert/strict";
import { describe, it } from "node:test";
// L'app usa questi helper da `@fantappero/contracts`; il file ha solo import di tipo e si carica dal sorgente.
import {
  roleQuotaBlockReason,
  roleQuotaErrorMessage,
  rosterRoleQuota,
} from "../../../../../packages/contracts/src/rosterQuota.ts";
import type { FantasyRosterSlot } from "@fantappero/contracts";
import { listoneSwipeDecision, roleTabLabel, type ListoneSwipeInput } from "./listoneSwipe.ts";

const FREE: ListoneSwipeInput = {
  owned: false,
  canRelease: false,
  busy: false,
  emptySlotsCount: 5,
  priceValid: true,
  quotaReason: null,
};

function slot(index: number, role: string | null): FantasyRosterSlot {
  return {
    id: `s-${index}`,
    slotIndex: index,
    athleteId: `a-${index}`,
    athleteName: null,
    photoUrl: null,
    clubName: null,
    role,
    purchaseCredits: 1,
    exceedsRoleQuota: false,
  };
}

const team = {
  slots: [...Array.from({ length: 10 }, (_, index) => slot(index, "A")), slot(10, "D"), { ...slot(11, null), athleteId: null }],
  composition: {
    status: "incomplete",
    filledSlots: 11,
    competitionCount: 1,
    requireComplete: false,
    validatedAt: null,
    limits: { rosterSize: 35, goalkeepers: 3, defenders: 11, midfielders: 11, forwards: 10 },
    counts: { P: 0, D: 1, C: 0, A: 10 },
    issues: [],
  },
};

describe("listoneSwipeDecision: scorrimento delle righe del listone", () => {
  it("libero con posto nel ruolo: a destra assegna", () => {
    assert.deepEqual(listoneSwipeDecision(FREE), { assign: true, release: false, blockedReason: null });
  });

  it("ruolo al completo: niente assegnazione, il motivo resta sulla riga", () => {
    const quotaReason = roleQuotaBlockReason(rosterRoleQuota(team), "A", { emptySlotsCount: 5 });
    assert.equal(quotaReason, "Attaccanti al completo: 10 su 10. Per prenderne un altro prima svincolane uno.");
    assert.deepEqual(listoneSwipeDecision({ ...FREE, quotaReason }), {
      assign: false,
      release: false,
      blockedReason: quotaReason,
    });
  });

  it("gli altri ruoli restano assegnabili", () => {
    const quotaReason = roleQuotaBlockReason(rosterRoleQuota(team), "D", { emptySlotsCount: 5 });
    assert.equal(quotaReason, null);
    assert.equal(listoneSwipeDecision({ ...FREE, quotaReason }).assign, true);
  });

  it("in rosa: si può ancora rimuovere anche con il ruolo pieno", () => {
    assert.deepEqual(
      listoneSwipeDecision({ ...FREE, owned: true, canRelease: true, quotaReason: "pieno" }),
      { assign: false, release: true, blockedReason: null },
    );
    assert.equal(listoneSwipeDecision({ ...FREE, owned: true, canRelease: false }).release, false);
    assert.equal(listoneSwipeDecision({ ...FREE, owned: true, canRelease: true, busy: true }).release, false);
  });

  it("rosa piena: come prima, nessun gesto e nessun messaggio nuovo", () => {
    assert.deepEqual(listoneSwipeDecision({ ...FREE, emptySlotsCount: 0, quotaReason: "pieno" }), {
      assign: false,
      release: false,
      blockedReason: null,
    });
  });

  it("prezzo non valido o operazione in corso: niente assegnazione", () => {
    assert.equal(listoneSwipeDecision({ ...FREE, priceValid: false }).assign, false);
    assert.deepEqual(listoneSwipeDecision({ ...FREE, busy: true, quotaReason: "pieno" }), {
      assign: false,
      release: false,
      blockedReason: null,
    });
  });

  it("rifiuto del server per quota: stesso testo da mostrare sulla riga", () => {
    const error = { code: "role_quota_exceeded", message: "Limite attaccanti raggiunto (10)." };
    assert.equal(
      roleQuotaErrorMessage(error, "A", rosterRoleQuota(team), { teamName: "Real Tiki" }),
      "Real Tiki ha già 10 attaccanti su 10.",
    );
  });
});

describe("roleTabLabel", () => {
  it("aggiunge il conto alla scheda del ruolo", () => {
    assert.equal(roleTabLabel("Attaccanti", { filled: 10, max: 10 }), "Attaccanti 10/10");
    assert.equal(roleTabLabel("Tutti", null), "Tutti");
  });
});
