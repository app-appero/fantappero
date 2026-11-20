import assert from "node:assert/strict";
import { describe, it } from "node:test";

import {
  passwordAutofill,
  registrationLoginFailure,
  registrationRequestBody,
  validateEmailRegistration,
} from "./emailRegistration.ts";

describe("passwordAutofill", () => {
  it("in registrazione la password è nuova (Android e iOS)", () => {
    assert.deepEqual(passwordAutofill("register"), {
      autoComplete: "new-password",
      textContentType: "newPassword",
    });
  });

  it("all'accesso è quella attuale", () => {
    assert.deepEqual(passwordAutofill("login"), {
      autoComplete: "current-password",
      textContentType: "password",
    });
  });
});

describe("validateEmailRegistration", () => {
  it("chiede tutti i campi", () => {
    const missing = "Compila tutti i campi obbligatori.";
    assert.equal(validateEmailRegistration({ displayName: "", email: "a@b.it", password: "x" }), missing);
    assert.equal(validateEmailRegistration({ displayName: "Marco", email: "  ", password: "x" }), missing);
    assert.equal(validateEmailRegistration({ displayName: "Marco", email: "a@b.it", password: "" }), missing);
  });

  it("senza conferma (scheda Registrati) basta compilare i tre campi", () => {
    assert.equal(validateEmailRegistration({ displayName: "Marco", email: "a@b.it", password: "segreta123" }), null);
  });

  it("con la conferma (schermata Registrati) le password devono coincidere", () => {
    const fields = { displayName: "Marco", email: "a@b.it", password: "segreta123" };
    assert.equal(validateEmailRegistration({ ...fields, confirmPassword: "altra" }), "Le password non coincidono.");
    assert.equal(validateEmailRegistration({ ...fields, confirmPassword: "segreta123" }), null);
  });
});

describe("registrationRequestBody", () => {
  it("toglie gli spazi a nome ed email, non alla password", () => {
    assert.deepEqual(
      registrationRequestBody({ displayName: " Marco Rossi ", email: " marco@esempio.it ", password: " pass " }),
      { displayName: "Marco Rossi", email: "marco@esempio.it", password: " pass " },
    );
  });
});

describe("registrationLoginFailure", () => {
  it("non tester: si apre la richiesta di accesso", () => {
    assert.deepEqual(registrationLoginFailure({ code: "tester_only" }, "x"), { kind: "tester_gate" });
  });

  it("conferma email accesa: resta su Registrati con «Controlla la tua email»", () => {
    assert.deepEqual(registrationLoginFailure({ code: "email_not_verified" }, "x"), {
      kind: "verify_email",
      tab: "registrati",
    });
  });

  it("password diversa da quella di un account già esistente: Accedi con un suggerimento", () => {
    const outcome = registrationLoginFailure({ code: "invalid_credentials" }, "Email o password non validi.");
    assert.equal(outcome.kind, "login_now");
    assert.ok(outcome.kind === "login_now" && outcome.tab === "accedi");
    assert.match(outcome.kind === "login_now" ? outcome.message : "", /Password dimenticata/);
  });

  it("altri errori: Accedi con il messaggio ricevuto", () => {
    assert.deepEqual(registrationLoginFailure({ code: "network_error" }, "Connessione non disponibile."), {
      kind: "login_now",
      tab: "accedi",
      message: "Connessione non disponibile.",
    });
    assert.deepEqual(registrationLoginFailure(null, "Accesso non riuscito."), {
      kind: "login_now",
      tab: "accedi",
      message: "Accesso non riuscito.",
    });
  });
});
