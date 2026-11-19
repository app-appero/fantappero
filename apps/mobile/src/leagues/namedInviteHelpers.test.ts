import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
  revocableInviteId,
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
