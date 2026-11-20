import type { RegisterRequest } from "@fantappero/contracts";
import type { AuthTab } from "./authScreenState";

/**
 * Registrazione con email: controlli del modulo e cosa fare dopo, condivisi dalla scheda
 * «Registrati» della schermata di accesso e da `AuthRegisterScreen`.
 */

export type RegistrationFields = {
  displayName: string;
  email: string;
  password: string;
  /** Solo dove il modulo chiede di ripetere la password (`AuthRegisterScreen`). */
  confirmPassword?: string;
};

/** Messaggio da mostrare se il modulo non è completo; `null` se si può inviare. */
export function validateEmailRegistration(fields: RegistrationFields): string | null {
  if (!fields.email.trim() || !fields.password || !fields.displayName.trim()) {
    return "Compila tutti i campi obbligatori.";
  }
  if (fields.confirmPassword !== undefined && fields.password !== fields.confirmPassword) {
    return "Le password non coincidono.";
  }
  return null;
}

/**
 * Suggerimenti di compilazione automatica del campo password (`autoComplete` per Android,
 * `textContentType` per iOS). In registrazione si sceglie una password nuova: il sistema
 * propone di generarla e salvarla, invece di proporre quella di un altro account. Come
 * `autocomplete="new-password"` nella scheda «Registrati» del web.
 */
export function passwordAutofill(purpose: "login" | "register"): {
  autoComplete: "current-password" | "new-password";
  textContentType: "password" | "newPassword";
} {
  return purpose === "register"
    ? { autoComplete: "new-password", textContentType: "newPassword" }
    : { autoComplete: "current-password", textContentType: "password" };
}

export function registrationRequestBody(fields: RegistrationFields): RegisterRequest {
  return {
    email: fields.email.trim(),
    password: fields.password,
    displayName: fields.displayName.trim(),
  };
}

/**
 * Dopo la registrazione si entra subito con la stessa email e password: su dev e pilota la
 * conferma dell'email è spenta e il server segna l'indirizzo come verificato. Se quell'accesso
 * non riesce, dice cosa mostrare:
 * - `tester_gate`: pilota in modalità test e l'indirizzo non è tra i tester, si apre la richiesta;
 * - `verify_email`: conferma email accesa (es. in locale): resta su Registrati con «Controlla la tua email»;
 * - `login_now`: si passa ad Accedi con l'email già scritta e il motivo.
 */
export type RegistrationLoginFailure =
  | { kind: "tester_gate" }
  | { kind: "verify_email"; tab: AuthTab }
  | { kind: "login_now"; tab: AuthTab; message: string };

export function registrationLoginFailure(error: unknown, fallbackMessage: string): RegistrationLoginFailure {
  const code = (error as { code?: unknown } | null)?.code;
  if (code === "tester_only") {
    return { kind: "tester_gate" };
  }
  if (code === "email_not_verified") {
    return { kind: "verify_email", tab: "registrati" };
  }
  if (code === "invalid_credentials") {
    // La risposta della registrazione è la stessa anche per un indirizzo già usato: se la
    // password non corrisponde, l'account c'era già.
    return {
      kind: "login_now",
      tab: "accedi",
      message: "Se hai già un account con questa email, accedi con la tua password oppure usa «Password dimenticata?».",
    };
  }
  return { kind: "login_now", tab: "accedi", message: fallbackMessage };
}
