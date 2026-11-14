import { BrandLogo, Button, Input, Textarea } from "@fantappero/ui";
import { type FormEvent, type ReactNode, useState } from "react";
import { submitTesterRequest } from "../../api/auth";
import { ApiError } from "../../api/client";
import { getApiErrorMessage } from "../../auth/AuthContext";

/** Cosa ha risposto l'accesso con Google a chi non è ancora tester. */
export type TesterGateInfo = {
  status: "none" | "pending" | "rejected";
  requestToken?: string;
  submittedAt?: string;
  /** Account Google a cui si riferisce la richiesta e nome da precompilare. */
  email?: string;
  name?: string;
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
    email: typeof error.payload.requestEmail === "string" ? error.payload.requestEmail : undefined,
    name: typeof error.payload.requestName === "string" ? error.payload.requestName : undefined,
  };
}

function formatDate(iso?: string): string {
  if (!iso) {
    return "";
  }
  const date = new Date(iso);
  return Number.isNaN(date.getTime()) ? "" : date.toLocaleDateString("it-IT");
}

function splitName(name?: string): { first: string; last: string } {
  const parts = (name ?? "").trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) {
    return { first: "", last: "" };
  }
  return { first: parts[0] ?? "", last: parts.slice(1).join(" ") };
}

const STEPS = [
  { title: "Invii la richiesta", detail: "Nome, cognome e telefono" },
  { title: "La valutiamo", detail: "Ti avvisiamo noi" },
  { title: "Entri nel gruppo", detail: "Poi accedi con lo stesso Google" },
] as const;

function TesterSteps({ current }: { current: number }) {
  return (
    <ol className="fa-tester-steps" aria-label="Come funziona">
      {STEPS.map((step, index) => {
        const state = index < current ? "done" : index === current ? "now" : "todo";
        return (
          <li key={step.title} className={`fa-tester-steps__item fa-tester-steps__item--${state}`}>
            <span className="fa-tester-steps__dot" aria-hidden="true">
              {state === "done" ? "✓" : index + 1}
            </span>
            <span>
              <strong>{step.title}</strong>
              <small>{step.detail}</small>
            </span>
          </li>
        );
      })}
    </ol>
  );
}

/** Pagina intera della richiesta: titolo e passi a sinistra, scheda con il modulo a destra. */
function TesterShell({
  current,
  children,
  testId,
}: {
  current: number;
  children: ReactNode;
  testId: string;
}) {
  return (
    <div className="fa-auth-page fa-tester-page" data-testid={testId}>
      <section className="fa-tester-page__intro">
        <BrandLogo variant="full" size="lg" />
        <h1 className="fa-tester-page__title">
          Il pilota è riservato ai <span>tester</span>
        </h1>
        <p className="fa-tester-page__lead">
          Stiamo provando il gioco con un gruppo ristretto. Chiedi di entrare: ti rispondiamo noi.
        </p>
        <TesterSteps current={current} />
      </section>
      <section className="fa-tester-card">{children}</section>
    </div>
  );
}

function GoogleAccountRow({ email, onBack }: { email?: string; onBack: () => void }) {
  if (!email) {
    return null;
  }
  return (
    <div className="fa-tester-account" data-testid="tester-request-account">
      <span className="fa-tester-account__g" aria-hidden="true">
        G
      </span>
      <span className="fa-tester-account__text">
        <small>Account Google</small>
        <strong>{email}</strong>
      </span>
      <button type="button" className="fa-tester-account__change" onClick={onBack}>
        Cambia
      </button>
    </div>
  );
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
  const prefill = splitName(info.name);
  const [firstName, setFirstName] = useState(prefill.first);
  const [lastName, setLastName] = useState(prefill.last);
  const [phone, setPhone] = useState("");
  const [motivation, setMotivation] = useState("");
  const [consent, setConsent] = useState(false);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sent, setSent] = useState(false);

  if (sent || info.status === "pending") {
    const date = formatDate(info.submittedAt) || (sent ? new Date().toLocaleDateString("it-IT") : "");
    return (
      <TesterShell current={1} testId="tester-request-pending">
        <div className="fa-tester-card__done" aria-hidden="true">
          ✓
        </div>
        <h2 className="fa-tester-card__title">
          {sent ? "Richiesta inviata!" : "Richiesta in valutazione"}
        </h2>
        <p className="fa-tester-card__text">
          {sent
            ? "Abbiamo ricevuto la tua richiesta."
            : `La tua richiesta${date ? ` del ${date}` : ""} è in valutazione.`}{" "}
          Quando verrà accolta potrai accedere con Google e ti aggiungeremo al gruppo WhatsApp dei
          tester. <strong>Non serve inviarla di nuovo.</strong>
        </p>
        <TesterSteps current={1} />
        {info.email || date ? (
          <p className="fa-tester-card__note">
            {date ? `Richiesta del ${date}` : null}
            {date && info.email ? " · " : null}
            {info.email ? <strong>{info.email}</strong> : null}
          </p>
        ) : null}
        <Button type="button" variant="secondary" onClick={onBack}>
          Torna alla home
        </Button>
      </TesterShell>
    );
  }

  if (info.status === "rejected") {
    return (
      <TesterShell current={1} testId="tester-request-rejected">
        <h2 className="fa-tester-card__title">Accesso non disponibile</h2>
        <p className="fa-tester-card__text">
          La tua richiesta è già stata valutata e per ora non è stata accolta. Potrai riprovare più
          avanti.
        </p>
        <Button type="button" variant="secondary" onClick={onBack}>
          Torna alla home
        </Button>
      </TesterShell>
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
    <TesterShell current={0} testId="tester-request-page">
      <form className="fa-tester-request" onSubmit={onSubmit} data-testid="tester-request-form">
        <p className="fa-tester-card__kick">
          <i aria-hidden="true" />
          Fase pilota · accesso su richiesta
        </p>
        <h2 className="fa-tester-card__title">
          Chiedi di <span>partecipare</span>
        </h2>
        <p className="fa-tester-card__text">
          L&apos;accesso al pilota è riservato ai tester. Lasciaci i tuoi dati: valuteremo la
          richiesta e, se accolta, entri con lo stesso account Google.
        </p>
        <GoogleAccountRow email={info.email} onBack={onBack} />
        <div className="fa-tester-request__names">
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
        </div>
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
    </TesterShell>
  );
}
