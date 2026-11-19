import { AuthFormLayout, Button, Tab, TabList, TabPanel, Tabs, UiStatePanel } from "@fantappero/ui";
import { type FormEvent, useState } from "react";
import { register as registerApi } from "../../api/auth";
import { ApiError } from "../../api/client";
import { getApiErrorMessage, useAuth } from "../../auth/AuthContext";
import { writeLastUser } from "../../auth/lastUser";
import { loadStoredSession } from "../../auth/sessionStorage";
import { Link, useLocation, useNavigate } from "../../router/simpleRouter";
import { testerGateFromError, type TesterGateInfo } from "./TesterRequestPanel";

export type EmailAuthTab = "accedi" | "registrati";

/**
 * Alternativa a Google per chi non ha un account Google: si apre sotto il tasto di Google, nella
 * stessa scheda, con le due schede «Accedi» e «Registrati». Un non tester che accede (o si
 * registra, con la verifica email spenta) vede la stessa richiesta di accesso di Google.
 */
export function EmailAuthPanel({
  tab,
  onTabChange,
  onClose,
  onTesterGate,
  verificationRequired,
  initialEmail = "",
}: {
  tab: EmailAuthTab;
  onTabChange: (tab: EmailAuthTab) => void;
  onClose: () => void;
  onTesterGate: (info: TesterGateInfo) => void;
  /** Con `false` (dev e pilota) dopo la registrazione si entra subito con le stesse credenziali. */
  verificationRequired: boolean;
  initialEmail?: string;
}) {
  const { login } = useAuth();
  const navigate = useNavigate();
  const { search } = useLocation();
  const [email, setEmail] = useState(initialEmail);
  const [password, setPassword] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // Verifica email accesa: dopo la registrazione si aspetta il messaggio, non si entra.
  const [checkEmailMessage, setCheckEmailMessage] = useState<string | null>(null);

  function selectTab(next: EmailAuthTab) {
    setError(null);
    setCheckEmailMessage(null);
    onTabChange(next);
  }

  /** Accede con email e password e va alla pagina richiesta (di solito le leghe). */
  async function signIn() {
    await login(email, password);
    const sessionUser = loadStoredSession()?.user;
    if (sessionUser?.displayName && email.trim()) {
      writeLastUser({ displayName: sessionUser.displayName, email: email.trim() });
    }
    const returnTo = new URLSearchParams(search).get("returnTo");
    navigate(returnTo ? decodeURIComponent(returnTo) : "/leghe");
  }

  /** Pilota in modalità test: un non tester può chiedere di partecipare, come con Google. */
  function openTesterGate(cause: unknown): boolean {
    const gate = testerGateFromError(cause);
    if (!gate) {
      return false;
    }
    onTesterGate({ ...gate, provider: "email" });
    return true;
  }

  async function handleLogin(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await signIn();
    } catch (cause) {
      if (!openTesterGate(cause)) {
        setError(getApiErrorMessage(cause, "Accesso non riuscito."));
      }
    } finally {
      setLoading(false);
    }
  }

  async function handleRegister(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    if (!email.trim() || !password || !displayName.trim()) {
      setError("Compila tutti i campi obbligatori.");
      return;
    }
    setLoading(true);
    try {
      const response = await registerApi({ email, password, displayName });
      if (verificationRequired) {
        setCheckEmailMessage(response.message);
        return;
      }
      // Verifica email spenta: l'account è già attivo, si entra subito.
      try {
        await signIn();
      } catch (cause) {
        if (openTesterGate(cause)) {
          return;
        }
        // Di solito l'indirizzo aveva già un account con un'altra password: si passa ad «Accedi».
        setPassword("");
        onTabChange("accedi");
        setError(
          cause instanceof ApiError && cause.code === "invalid_credentials"
            ? "Accesso non riuscito: se avevi già un account, accedi con la tua password."
            : getApiErrorMessage(cause, "Accesso non riuscito: riprova da «Accedi»."),
        );
      }
    } catch (cause) {
      setError(getApiErrorMessage(cause, "Registrazione non riuscita."));
    } finally {
      setLoading(false);
    }
  }

  const privacyLine = (verb: string) => (
    <p className="fa-auth-layout__register" data-testid="login-privacy-link">
      {verb} accetti l&apos;<Link to="/privacy">informativa privacy</Link>.
    </p>
  );

  return (
    <div className="fa-login-email" data-testid="auth-email-panel">
      <Tabs
        value={tab}
        onValueChange={(next) => selectTab(next === "registrati" ? "registrati" : "accedi")}
        aria-label="Accedi o registrati"
        className="fa-login-email__tabs"
      >
        <div className="fa-login-email__head">
          <TabList>
            <Tab value="accedi" testId="auth-email-tab-login">
              Accedi
            </Tab>
            <Tab value="registrati" testId="auth-email-tab-register">
              Registrati
            </Tab>
          </TabList>
          <Button
            variant="ghost"
            size="sm"
            className="fa-login-email__close"
            onClick={onClose}
            data-testid="auth-email-close"
          >
            Chiudi
          </Button>
        </div>
        <TabPanel value="accedi">
          <AuthFormLayout
            brand={null}
            hideBrand
            title=""
            submitLabel="Accedi"
            email={email}
            password={password}
            onEmailChange={setEmail}
            onPasswordChange={setPassword}
            onSubmit={handleLogin}
            loading={loading}
            error={error ?? undefined}
            forgotPasswordLink={
              <p className="fa-auth-layout__forgot">
                <Link to="/accedi/recupera">Password dimenticata?</Link>
              </p>
            }
            registerPrompt={privacyLine("Accedendo")}
          />
        </TabPanel>
        <TabPanel value="registrati">
          {checkEmailMessage ? (
            <div className="fa-login-email__done">
              <UiStatePanel
                state="success"
                title="Controlla la tua email"
                message={checkEmailMessage}
                testId="auth-register-success"
              />
              <Button variant="secondary" onClick={() => selectTab("accedi")}>
                Vai ad Accedi
              </Button>
            </div>
          ) : (
            <AuthFormLayout
              brand={null}
              hideBrand
              title=""
              submitLabel="Crea account"
              showDisplayName
              email={email}
              password={password}
              displayName={displayName}
              onEmailChange={setEmail}
              onPasswordChange={setPassword}
              onDisplayNameChange={setDisplayName}
              onSubmit={handleRegister}
              loading={loading}
              error={error ?? undefined}
              registerPrompt={privacyLine("Registrandoti")}
            />
          )}
        </TabPanel>
      </Tabs>
    </div>
  );
}
