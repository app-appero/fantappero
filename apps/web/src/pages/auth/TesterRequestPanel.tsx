import { Button, Input, Textarea } from "@fantappero/ui";
import { type FormEvent, useState } from "react";
import { submitTesterRequest } from "../../api/auth";
import { ApiError } from "../../api/client";
import { getApiErrorMessage } from "../../auth/AuthContext";

/** Cosa ha risposto l'accesso con Google a chi non è ancora tester. */
export type TesterGateInfo = {
  status: "none" | "pending" | "rejected";
  requestToken?: string;
  submittedAt?: string;
};

/** Se l'errore è il rifiuto `tester_only` dell'accesso con Google, dice a che punto è la richiesta. */
export function testerGateFromError(error: unknown): TesterGateInfo | null {
  if (!(error instanceof ApiError) || error.code !== "tester_only") {
    return null;
  }
  const status = error.payload.requestStatus;
  return {
    status: status === "pending" || status === "rejected" ? status : "none",
    requestToken:
      typeof error.payload.requestToken === "string" ? error.payload.requestToken : undefined,
    submittedAt:
      typeof error.payload.requestSubmittedAt === "string"
        ? error.payload.requestSubmittedAt
        : undefined,
  };
}

function formatDate(iso?: string): string {
  if (!iso) {
    return "";
  }
  const date = new Date(iso);
  return Number.isNaN(date.getTime()) ? "" : date.toLocaleDateString("it-IT");
}

/**
 * Pilota in modalità test: chi non è tra i tester non crea nessun account, ma può chiedere di
 * partecipare. Il numero di telefono serve solo per aggiungere la persona al gruppo WhatsApp.
 */
export function TesterRequestPanel({
  info,
  onBack,
}: {
  info: TesterGateInfo;
  onBack: () => void;
}) {
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [phone, setPhone] = useState("");
  const [motivation, setMotivation] = useState("");
  const [consent, setConsent] = useState(false);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sent, setSent] = useState(false);

  if (sent || info.status === "pending") {
    const date = formatDate(info.submittedAt);
    return (
      <div className="fa-tester-request" data-testid="tester-request-pending">
        <h2>Richiesta in valutazione</h2>
        <p>
          {sent
            ? "Abbiamo ricevuto la tua richiesta."
            : `La tua richiesta${date ? ` del ${date}` : ""} è in valutazione.`}{" "}
          Quando verrà accolta potrai accedere con Google come tutti gli altri tester: riprova più
          tardi, non serve inviarla di nuovo.
        </p>
        <Button type="button" variant="secondary" onClick={onBack}>
          Torna indietro
        </Button>
      </div>
    );
  }

  if (info.status === "rejected") {
    return (
      <div className="fa-tester-request" data-testid="tester-request-rejected">
        <h2>Accesso non disponibile</h2>
        <p>
          La tua richiesta è già stata valutata e per ora non è stata accolta. Potrai riprovare più
          avanti.
        </p>
        <Button type="button" variant="secondary" onClick={onBack}>
          Torna indietro
        </Button>
      </div>
    );
  }

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    if (!info.requestToken) {
      setError("Sessione scaduta: accedi di nuovo con Google.");
      return;
    }
    setSending(true);
    setError(null);
    try {
      await submitTesterRequest({
        requestToken: info.requestToken,
        firstName,
        lastName,
        phone,
        motivation: motivation.trim() ? motivation : null,
        consent,
      });
      setSent(true);
    } catch (cause) {
      setError(getApiErrorMessage(cause, "Impossibile inviare la richiesta."));
    } finally {
      setSending(false);
    }
  }

  return (
    <form className="fa-tester-request" onSubmit={onSubmit} data-testid="tester-request-form">
      <h2>FantApperò è in fase di test</h2>
      <p>
        L&apos;accesso è riservato ai tester. Se vuoi partecipare lascia i tuoi dati: valuteremo la
        richiesta e, se accolta, potrai accedere con lo stesso account Google.
      </p>
      <Input
        label="Nome"
        value={firstName}
        onChange={(event) => setFirstName(event.target.value)}
        required
        maxLength={80}
        autoComplete="given-name"
        data-testid="tester-request-first-name"
      />
      <Input
        label="Cognome"
        value={lastName}
        onChange={(event) => setLastName(event.target.value)}
        required
        maxLength={80}
        autoComplete="family-name"
        data-testid="tester-request-last-name"
      />
      <Input
        label="Numero di telefono"
        type="tel"
        value={phone}
        onChange={(event) => setPhone(event.target.value)}
        required
        maxLength={30}
        autoComplete="tel"
        hint="Lo useremo solo per aggiungerti al gruppo WhatsApp dei tester, per nessun altro scopo."
        data-testid="tester-request-phone"
      />
      <Textarea
        label="Perché vuoi partecipare? (facoltativo)"
        value={motivation}
        onChange={(event) => setMotivation(event.target.value)}
        maxLength={1000}
        rows={4}
        data-testid="tester-request-motivation"
      />
      <label className="fa-tester-request__consent">
        <input
          type="checkbox"
          checked={consent}
          onChange={(event) => setConsent(event.target.checked)}
          data-testid="tester-request-consent"
        />
        <span>
          Acconsento al trattamento di questi dati per valutare la richiesta e, se accolta, per
          aggiungermi al gruppo WhatsApp dei tester. Se la richiesta non viene accolta i dati si
          cancellano entro 30 giorni.
        </span>
      </label>
      {error ? (
        <p role="alert" className="fa-field__error" data-testid="tester-request-error">
          {error}
        </p>
      ) : null}
      <div className="fa-tester-request__actions">
        <Button type="submit" loading={sending} disabled={!consent} data-testid="tester-request-submit">
          Invia richiesta
        </Button>
        <Button type="button" variant="ghost" onClick={onBack}>
          Annulla
        </Button>
      </div>
    </form>
  );
}
