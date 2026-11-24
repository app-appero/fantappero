import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { describe, it } from "node:test";
import {
  inviteErrorRefreshesRow,
  revocableInviteId,
  revokeErrorRefreshesRow,
  revokeInviteConfirmMessage,
  revokeInviteErrorMessage,
} from "./namedInviteHelpers.ts";

describe("revocableInviteId", () => {
  it("restituisce l'id solo per un invito pendente con id", () => {
    assert.equal(
      revocableInviteId({ namedInviteStatus: "pending", namedInviteId: "invite-1" }),
      "invite-1",
    );
  });

  it("senza id (backend precedente) non propone l'annullamento", () => {
    assert.equal(revocableInviteId({ namedInviteStatus: "pending" }), null);
    assert.equal(revocableInviteId({ namedInviteStatus: "pending", namedInviteId: null }), null);
    assert.equal(revocableInviteId({ namedInviteStatus: "pending", namedInviteId: "  " }), null);
  });

  it("ignora inviti non più pendenti", () => {
    for (const status of ["accepted", "declined", "revoked", "expired"] as const) {
      assert.equal(revocableInviteId({ namedInviteStatus: status, namedInviteId: "invite-1" }), null);
    }
    assert.equal(revocableInviteId({ namedInviteStatus: null, namedInviteId: null }), null);
  });

  it("ignora sé stessi e chi è già in lega", () => {
    assert.equal(
      revocableInviteId({ namedInviteStatus: "pending", namedInviteId: "invite-1", isSelf: true }),
      null,
    );
    assert.equal(
      revocableInviteId({ namedInviteStatus: "pending", namedInviteId: "invite-1", inLeague: true }),
      null,
    );
  });
});

describe("revokeInviteConfirmMessage", () => {
  it("nomina il fantallenatore e dice che si può reinvitare", () => {
    const message = revokeInviteConfirmMessage("Pina");
    assert.match(message, /^Pina /);
    assert.match(message, /invitarlo di nuovo/);
  });
});

describe("revokeInviteErrorMessage", () => {
  it("traduce gli errori noti della revoca", () => {
    assert.match(revokeInviteErrorMessage({ status: 403, code: "forbidden" }) ?? "", /permessi/);
    assert.match(
      revokeInviteErrorMessage({ status: 400, code: "named_invite_not_pending" }) ?? "",
      /non è più annullabile/,
    );
    assert.equal(
      revokeInviteErrorMessage({ status: 400, code: "named_invite_not_found" }),
      "Invito non trovato.",
    );
  });

  it("lascia al chiamante gli altri errori", () => {
    assert.equal(revokeInviteErrorMessage({ status: 500, code: "internal_error" }), null);
    assert.equal(revokeInviteErrorMessage(new Error("rete")), null);
    assert.equal(revokeInviteErrorMessage(null), null);
  });
});

describe("inviteErrorRefreshesRow", () => {
  it("dopo «Invito già inviato» (o una riga comunque vecchia) la directory si ricarica", () => {
    assert.equal(inviteErrorRefreshesRow({ code: "named_invite_already_pending" }), true);
    assert.equal(inviteErrorRefreshesRow({ code: "already_member" }), true);
    assert.equal(inviteErrorRefreshesRow({ code: "recipient_unavailable" }), true);
  });

  it("gli altri errori non toccano la riga", () => {
    assert.equal(inviteErrorRefreshesRow({ code: "league_full" }), false);
    assert.equal(inviteErrorRefreshesRow({ code: "internal_error" }), false);
    assert.equal(inviteErrorRefreshesRow(new Error("rete")), false);
    assert.equal(inviteErrorRefreshesRow(null), false);
  });
});

describe("revokeErrorRefreshesRow", () => {
  it("invito già risposto, scaduto o sparito: la riga si riallinea", () => {
    assert.equal(revokeErrorRefreshesRow({ code: "named_invite_not_pending" }), true);
    assert.equal(revokeErrorRefreshesRow({ code: "named_invite_not_found" }), true);
  });

  it("gli altri errori non toccano la riga", () => {
    assert.equal(revokeErrorRefreshesRow({ code: "internal_error" }), false);
    assert.equal(revokeErrorRefreshesRow(new Error("rete")), false);
    assert.equal(revokeErrorRefreshesRow(null), false);
  });
});

describe("directory: riga vecchia, si rilegge anche il conto degli inviti (QA notturna 23→24/11)", () => {
  const source = readFileSync(new URL("../components/CoachDirectoryPanel.tsx", import.meta.url), "utf8");

  /** Corpo del ramo `if` che parte da `header`, fino alla graffa che lo chiude. */
  function branch(header: string): string {
    const start = source.indexOf(header);
    assert.ok(start >= 0, `manca ${header}`);
    const end = source.indexOf("\n      }", start);
    assert.ok(end > start, `ramo non chiuso: ${header}`);
    return source.slice(start, end);
  }

  it("dopo «Invito già inviato» da un'altra scheda: riga, poi «· 1 invito in attesa» e banner", () => {
    assert.match(
      branch("if (error instanceof ApiError && inviteErrorRefreshesRow(error)) {"),
      /await load\(\{ silent: true \}\);\s*onInvitesChanged\?\.\(\);/,
    );
  });

  it("dopo una revoca da una riga vecchia: riga, poi conto e banner", () => {
    assert.match(
      branch("if (revokeErrorRefreshesRow(apiError)) {"),
      /await load\(\{ silent: true \}\);\s*onInvitesChanged\?\.\(\);/,
    );
  });
});
