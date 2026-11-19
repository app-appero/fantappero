import type { TesterRequestBody, TesterRequestStatus } from "@fantappero/contracts";

/**
 * Pilota in modalità test: chi non è tra i tester riceve il rifiuto `tester_only` con lo stato
 * della richiesta di accesso (stesso contenuto dell'accesso con Google, vedi
 * `_assert_tester_allowed_google` nel backend). Qui le parti senza React della richiesta,
 * allineate a `apps/web/src/pages/auth/TesterRequestPanel.tsx`.
 */

export type TesterGateInfo = {
  status: TesterRequestStatus;
  /** Gettone firmato per inviare la richiesta: c'è solo con `status` = `none`. */
  requestToken?: string;
  /** Quando è stata inviata la richiesta già presente (`pending` / `rejected`). */
  submittedAt?: string;
  /** Account a cui si riferisce la richiesta. */
  email?: string;
  /** Nome da precompilare (intero, oppure già diviso in nome e cognome). */
  name?: string;
  firstName?: string;
  lastName?: string;
};

function optionalString(value: unknown): string | undefined {
  return typeof value === "string" && value.trim() ? value : undefined;
}

/**
 * Se l'errore è il rifiuto `tester_only`, dice a che punto è la richiesta; altrimenti `null`.
 * Si legge per forma (`code` e `payload` di `ApiError`) per non dipendere dal client HTTP.
 */
export function testerGateFromError(error: unknown): TesterGateInfo | null {
  if (!error || typeof error !== "object" || (error as { code?: unknown }).code !== "tester_only") {
    return null;
  }
  const rawPayload = (error as { payload?: unknown }).payload;
  const payload = rawPayload && typeof rawPayload === "object" ? (rawPayload as Record<string, unknown>) : {};
  const status = payload.requestStatus;
  return {
    status: status === "pending" || status === "rejected" ? status : "none",
    requestToken: optionalString(payload.requestToken),
    submittedAt: optionalString(payload.requestSubmittedAt),
    email: optionalString(payload.requestEmail),
    name: optionalString(payload.requestName),
    firstName: optionalString(payload.requestFirstName),
    lastName: optionalString(payload.requestLastName),
  };
}

/** Nome e cognome da precompilare: quelli separati se ci sono, altrimenti dal nome intero. */
export function testerRequestPrefill(info: TesterGateInfo): { firstName: string; lastName: string } {
  const parts = (info.name ?? "").trim().split(/\s+/).filter(Boolean);
  return {
    firstName: info.firstName?.trim() || (parts[0] ?? ""),
    lastName: info.lastName?.trim() || parts.slice(1).join(" "),
  };
}

export type TesterRequestFields = {
  firstName: string;
  lastName: string;
  phone: string;
  motivation: string;
  consent: boolean;
};

/** Corpo per `POST /auth/tester-requests`, oppure il motivo per cui non si può ancora inviare. */
export function buildTesterRequestBody(
  info: TesterGateInfo,
  fields: TesterRequestFields,
): { ok: true; body: TesterRequestBody } | { ok: false; error: string } {
  if (!info.requestToken) {
    return {
      ok: false,
      error: "Non riesco a inviare la richiesta da questa schermata: torna indietro e accedi di nuovo.",
    };
  }
  const firstName = fields.firstName.trim();
  const lastName = fields.lastName.trim();
  if (!firstName || !lastName) {
    return { ok: false, error: "Inserisci nome e cognome." };
  }
  if (!fields.consent) {
    return { ok: false, error: "Per inviare la richiesta serve il consenso al trattamento dei dati." };
  }
  const phone = fields.phone.trim();
  const motivation = fields.motivation.trim();
  return {
    ok: true,
    body: {
      requestToken: info.requestToken,
      firstName,
      lastName,
      phone: phone || null,
      motivation: motivation || null,
      consent: true,
    },
  };
}

/** Data della richiesta come «19/11/2026»; vuota se manca o non è valida. */
export function formatTesterRequestDate(iso: string | undefined): string {
  if (!iso) {
    return "";
  }
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) {
    return "";
  }
  const day = String(date.getDate()).padStart(2, "0");
  const month = String(date.getMonth() + 1).padStart(2, "0");
  return `${day}/${month}/${date.getFullYear()}`;
}
