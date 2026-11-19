import assert from "node:assert/strict";
import { describe, it } from "node:test";

import {
  buildTesterRequestBody,
  formatTesterRequestDate,
  testerGateFromError,
  testerRequestPrefill,
  type TesterGateInfo,
} from "./testerGate.ts";

/** Come `ApiError` di `@fantappero/api-client`: `code` e il corpo JSON in `payload`. */
function apiError(code: string, payload: Record<string, unknown>) {
  return Object.assign(new Error("Non autorizzato: l'accesso è riservato ai tester del pilota."), {
    status: 403,
    code,
    payload: { code, ...payload },
  });
}

describe("testerGateFromError", () => {
  it("legge il rifiuto tester_only di chi non ha ancora chiesto", () => {
    const gate = testerGateFromError(
      apiError("tester_only", {
        requestStatus: "none",
        requestEmail: "marco@esempio.it",
        requestName: "Marco Rossi",
        requestToken: "gettone-firmato",
      }),
    );
    assert.deepEqual(gate, {
      status: "none",
      requestToken: "gettone-firmato",
      submittedAt: undefined,
      email: "marco@esempio.it",
      name: "Marco Rossi",
      firstName: undefined,
      lastName: undefined,
    });
  });

  it("richiesta in valutazione o rifiutata: niente gettone, c'è la data", () => {
    const pending = testerGateFromError(
      apiError("tester_only", { requestStatus: "pending", requestSubmittedAt: "2026-11-18T10:00:00+00:00" }),
    );
    assert.equal(pending?.status, "pending");
    assert.equal(pending?.requestToken, undefined);
    assert.equal(pending?.submittedAt, "2026-11-18T10:00:00+00:00");
    assert.equal(testerGateFromError(apiError("tester_only", { requestStatus: "rejected" }))?.status, "rejected");
  });

  it("stato sconosciuto o assente vale come «none»", () => {
    assert.equal(testerGateFromError(apiError("tester_only", { requestStatus: "boh" }))?.status, "none");
    assert.equal(testerGateFromError({ code: "tester_only" })?.status, "none");
  });

  it("ignora gli altri errori", () => {
    assert.equal(testerGateFromError(apiError("invalid_credentials", {})), null);
    assert.equal(testerGateFromError(new Error("boom")), null);
    assert.equal(testerGateFromError(null), null);
    assert.equal(testerGateFromError("tester_only"), null);
  });

  it("scarta campi vuoti o non testuali", () => {
    const gate = testerGateFromError(apiError("tester_only", { requestToken: "", requestEmail: 42, requestName: "  " }));
    assert.equal(gate?.requestToken, undefined);
    assert.equal(gate?.email, undefined);
    assert.equal(gate?.name, undefined);
  });
});

describe("testerRequestPrefill", () => {
  it("usa nome e cognome separati se ci sono", () => {
    assert.deepEqual(
      testerRequestPrefill({ status: "none", name: "Marco Rossi", firstName: "Marco Aurelio", lastName: "Rossi" }),
      { firstName: "Marco Aurelio", lastName: "Rossi" },
    );
  });

  it("altrimenti divide il nome intero: la prima parola è il nome", () => {
    assert.deepEqual(testerRequestPrefill({ status: "none", name: "  Maria  De Luca " }), {
      firstName: "Maria",
      lastName: "De Luca",
    });
    assert.deepEqual(testerRequestPrefill({ status: "none", name: "Maria" }), { firstName: "Maria", lastName: "" });
    assert.deepEqual(testerRequestPrefill({ status: "none" }), { firstName: "", lastName: "" });
  });
});

describe("buildTesterRequestBody", () => {
  const info: TesterGateInfo = { status: "none", requestToken: "gettone-firmato" };
  const fields = { firstName: " Marco ", lastName: " Rossi ", phone: "  ", motivation: "", consent: true };

  it("prepara il corpo per POST /auth/tester-requests", () => {
    assert.deepEqual(buildTesterRequestBody(info, fields), {
      ok: true,
      body: {
        requestToken: "gettone-firmato",
        firstName: "Marco",
        lastName: "Rossi",
        phone: null,
        motivation: null,
        consent: true,
      },
    });
  });

  it("tiene telefono e motivazione se scritti", () => {
    const built = buildTesterRequestBody(info, { ...fields, phone: " 333 1234567 ", motivation: " Gioco da anni " });
    assert.ok(built.ok);
    assert.equal(built.ok && built.body.phone, "333 1234567");
    assert.equal(built.ok && built.body.motivation, "Gioco da anni");
  });

  it("senza gettone non si può inviare", () => {
    const built = buildTesterRequestBody({ status: "none" }, fields);
    assert.equal(built.ok, false);
    assert.match(built.ok ? "" : built.error, /accedi di nuovo/);
  });

  it("servono nome, cognome e consenso", () => {
    assert.deepEqual(buildTesterRequestBody(info, { ...fields, lastName: " " }), {
      ok: false,
      error: "Inserisci nome e cognome.",
    });
    const noConsent = buildTesterRequestBody(info, { ...fields, consent: false });
    assert.equal(noConsent.ok, false);
    assert.match(noConsent.ok ? "" : noConsent.error, /consenso/);
  });
});

describe("formatTesterRequestDate", () => {
  it("scrive la data all'italiana", () => {
    assert.equal(formatTesterRequestDate(new Date(2026, 10, 5, 12).toISOString()), "05/11/2026");
  });

  it("vuota se manca o non è valida", () => {
    assert.equal(formatTesterRequestDate(undefined), "");
    assert.equal(formatTesterRequestDate("non una data"), "");
  });
});
