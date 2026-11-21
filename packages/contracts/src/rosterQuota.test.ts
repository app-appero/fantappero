import assert from "node:assert/strict";
import { describe, it } from "node:test";
import type { FantasyRosterSlot } from "./leagues.ts";
import {
  fullRoleQuotas,
  fullRolesSummary,
  isRoleQuotaFull,
  listoneQuotaNotice,
  roleQuotaBlockReason,
  roleQuotaBlockedLabel,
  roleQuotaCountLabel,
  roleQuotaErrorMessage,
  roleQuotaFullMessage,
  rosterRoleQuota,
  type RoleQuotaTeam,
} from "./rosterQuota.ts";

const LIMITS = { rosterSize: 35, goalkeepers: 3, defenders: 11, midfielders: 11, forwards: 10 };

function slot(index: number, role: string | null, extra: Partial<FantasyRosterSlot> = {}): FantasyRosterSlot {
  return {
    id: `s-${index}`,
    slotIndex: index,
    athleteId: `a-${index}`,
    athleteName: `Calciatore ${index}`,
    photoUrl: null,
    clubName: null,
    role,
    purchaseCredits: 1,
    exceedsRoleQuota: false,
    ...extra,
  };
}

function team(roles: Array<string | null>, extraSlots: FantasyRosterSlot[] = []): RoleQuotaTeam {
  const slots = roles.map((role, index) => slot(index, role));
  const empty: FantasyRosterSlot = { ...slot(roles.length, null), athleteId: null, athleteName: null };
  return {
    slots: [...slots, ...extraSlots, empty],
    composition: {
      status: "incomplete",
      filledSlots: slots.length,
      competitionCount: 1,
      requireComplete: false,
      validatedAt: null,
      limits: { ...LIMITS },
      counts: { P: 0, D: 0, C: 0, A: 0 },
      issues: [],
    },
  };
}

const tenForwards = Array.from({ length: 10 }, () => "A");

describe("rosterRoleQuota: stessa regola del server", () => {
  it("conta i calciatori per ruolo e ignora gli slot vuoti", () => {
    const quota = rosterRoleQuota(team(["P", "D", "D", "A"]))!;
    assert.deepEqual(quota.roles.P, { role: "P", filled: 1, max: 3, full: false });
    assert.deepEqual(quota.roles.D, { role: "D", filled: 2, max: 11, full: false });
    assert.equal(quota.roles.A.filled, 1);
    assert.equal(quota.unresolved, 0);
  });

  it("un ruolo è pieno al limite: 10 attaccanti su 10", () => {
    const quota = rosterRoleQuota(team(tenForwards))!;
    assert.deepEqual(quota.roles.A, { role: "A", filled: 10, max: 10, full: true });
    assert.equal(isRoleQuotaFull(quota, "A"), true);
    assert.equal(isRoleQuotaFull(quota, "D"), false);
  });

  it("gli esuberi segnati contano: 11 su 10 resta pieno", () => {
    const quota = rosterRoleQuota(
      team(tenForwards, [slot(40, "A", { exceedsRoleQuota: true })]),
    )!;
    assert.deepEqual(quota.roles.A, { role: "A", filled: 11, max: 10, full: true });
  });

  it("chi non ha un ruolo conta in ogni ruolo, come per il server", () => {
    const quota = rosterRoleQuota(team(["P", "P", null]))!;
    assert.equal(quota.unresolved, 1);
    assert.deepEqual(quota.roles.P, { role: "P", filled: 3, max: 3, full: true });
    assert.equal(quota.roles.A.filled, 1);
    assert.equal(quota.roles.A.full, false);
  });

  it("un ruolo sconosciuto vale come senza ruolo", () => {
    const quota = rosterRoleQuota(team(["X"]))!;
    assert.equal(quota.unresolved, 1);
    assert.equal(quota.roles.D.filled, 1);
  });

  it("limite 0: il ruolo è pieno anche senza calciatori", () => {
    const base = team([]);
    const quota = rosterRoleQuota({
      ...base,
      composition: { ...base.composition!, limits: { ...LIMITS, goalkeepers: 0 } },
    })!;
    assert.equal(quota.roles.P.full, true);
  });

  it("senza limiti della lega non decide nulla", () => {
    assert.equal(rosterRoleQuota(null), null);
    assert.equal(rosterRoleQuota({ ...team(tenForwards), composition: null }), null);
    assert.equal(isRoleQuotaFull(null, "A"), false);
    assert.deepEqual(fullRoleQuotas(null), []);
    assert.equal(fullRolesSummary(null), null);
  });
});

describe("ruoli al completo e messaggi", () => {
  it("elenca i ruoli pieni in ordine P–D–C–A per la scheda «Tutti»", () => {
    const quota = rosterRoleQuota(team([...tenForwards, "P", "P", "P"]))!;
    assert.deepEqual(
      fullRoleQuotas(quota).map((stat) => stat.role),
      ["P", "A"],
    );
    assert.equal(fullRolesSummary(quota), "Al completo: Portieri (3/3), Attaccanti (10/10)");
    assert.equal(fullRolesSummary(rosterRoleQuota(team(["A"]))), null);
  });

  it("testo per la propria rosa e per la squadra di un altro", () => {
    const stat = { role: "A" as const, filled: 10, max: 10 };
    assert.equal(
      roleQuotaFullMessage(stat),
      "Attaccanti al completo: 10 su 10. Per prenderne un altro prima svincolane uno.",
    );
    assert.equal(roleQuotaFullMessage(stat, { teamName: "Real Tiki" }), "Real Tiki ha già 10 attaccanti su 10.");
    assert.equal(roleQuotaCountLabel(stat), "10/10");
    assert.equal(
      roleQuotaBlockedLabel("Lautaro", roleQuotaFullMessage(stat)),
      "Non puoi assegnare Lautaro. Attaccanti al completo: 10 su 10. Per prenderne un altro prima svincolane uno.",
    );
  });

  it("dice quando nel conto c'è chi non ha un ruolo", () => {
    const quota = rosterRoleQuota(team(["P", "P", null]))!;
    assert.equal(
      roleQuotaFullMessage(quota.roles.P, { unresolved: quota.unresolved }),
      "Portieri al completo: 3 su 3. Per prenderne un altro prima svincolane uno." +
        " Nel conto c'è anche 1 calciatore senza ruolo nel listone.",
    );
  });
});

describe("avviso in cima al listone e motivo per riga", () => {
  const quota = rosterRoleQuota(team([...tenForwards, "D"]))!;

  it("scheda del ruolo pieno: avviso; altri ruoli: niente", () => {
    assert.equal(
      listoneQuotaNotice(quota, "A", { emptySlotsCount: 5 }),
      "Attaccanti al completo: 10 su 10. Per prenderne un altro prima svincolane uno.",
    );
    assert.equal(
      listoneQuotaNotice(quota, "A", { emptySlotsCount: 5, teamName: "Real Tiki" }),
      "Real Tiki ha già 10 attaccanti su 10.",
    );
    assert.equal(listoneQuotaNotice(quota, "D", { emptySlotsCount: 5 }), null);
    assert.equal(listoneQuotaNotice(quota, "all", { emptySlotsCount: 5 }), "Al completo: Attaccanti (10/10)");
  });

  it("riga: bloccati solo i calciatori del ruolo pieno", () => {
    assert.match(roleQuotaBlockReason(quota, "A", { emptySlotsCount: 5 }) ?? "", /^Attaccanti al completo/);
    assert.equal(roleQuotaBlockReason(quota, "D", { emptySlotsCount: 5 }), null);
    assert.equal(roleQuotaBlockReason(null, "A", { emptySlotsCount: 5 }), null);
  });

  it("rosa piena: comportamento di sempre, nessun avviso di ruolo", () => {
    assert.equal(listoneQuotaNotice(quota, "A", { emptySlotsCount: 0 }), null);
    assert.equal(listoneQuotaNotice(quota, "all", { emptySlotsCount: 0 }), null);
    assert.equal(roleQuotaBlockReason(quota, "A", { emptySlotsCount: 0 }), null);
  });
});

describe("roleQuotaErrorMessage: l'errore del server con il testo del client", () => {
  const quota = rosterRoleQuota(team(Array.from({ length: 9 }, () => "A")))!;

  it("rifiuto per quota: stesso testo del client, anche se il conto del client era indietro", () => {
    const error = { code: "role_quota_exceeded", message: "Limite attaccanti raggiunto (10)." };
    assert.equal(
      roleQuotaErrorMessage(error, "A", quota),
      "Attaccanti al completo: 10 su 10. Per prenderne un altro prima svincolane uno.",
    );
    assert.equal(
      roleQuotaErrorMessage(error, "A", quota, { teamName: "Real Tiki" }),
      "Real Tiki ha già 10 attaccanti su 10.",
    );
  });

  it("tiene la spiegazione del server su chi non ha un ruolo", () => {
    const error = {
      code: "role_quota_exceeded",
      message:
        "Limite attaccanti raggiunto (10): Rossi non ha un ruolo nel listone e finché non lo riceve conta tra gli attaccanti.",
    };
    assert.equal(
      roleQuotaErrorMessage(error, "A", quota),
      "Attaccanti al completo: 10 su 10. Per prenderne un altro prima svincolane uno." +
        " Rossi non ha un ruolo nel listone e finché non lo riceve conta tra gli attaccanti.",
    );
  });

  it("usa il limite del client se il messaggio del server non lo porta", () => {
    const error = { code: "role_quota_exceeded", message: "" };
    assert.equal(roleQuotaErrorMessage(error, "A", quota, { teamName: "Real Tiki" }), "Real Tiki ha già 10 attaccanti su 10.");
  });

  it("altri errori o ruolo ignoto: nessuna traduzione", () => {
    assert.equal(roleQuotaErrorMessage({ code: "role_unresolved", message: "x" }, "A", quota), null);
    assert.equal(roleQuotaErrorMessage(new Error("rete"), "A", quota), null);
    assert.equal(roleQuotaErrorMessage(null, "A", quota), null);
    assert.equal(roleQuotaErrorMessage({ code: "role_quota_exceeded", message: "" }, undefined, quota), null);
    assert.equal(roleQuotaErrorMessage({ code: "role_quota_exceeded", message: "" }, "A", null), null);
  });
});
