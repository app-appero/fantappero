import { AuthFormLayout, BrandLogo, PageContainer, UiStatePanel } from "@fantappero/ui";
import { type FormEvent, useCallback, useEffect, useRef, useState } from "react";
import {
  forgotPassword,
  register as registerApi,
  resetPassword,
  verifyEmail,
} from "../../api/auth";
import { getApiErrorMessage, useAuth } from "../../auth/AuthContext";
import { googleAppHandoffUrl, googleAppReturnUrl } from "../../auth/googleAppReturn";
import { renderGoogleButton } from "../../auth/googleIdentity";
import { clearLastUser, initialsOf, readLastUser, writeLastUser, type LastUser } from "../../auth/lastUser";
import { loadStoredSession } from "../../auth/sessionStorage";
import { getWebEnv } from "../../config/env";
import { Link, useLocation, useNavigate } from "../../router/simpleRouter";

/** "Continua con Google" — hidden when VITE_GOOGLE_CLIENT_ID is unset. */
function GoogleSignInButton({
  onError,
  onCredential,
}: {
  onError: (message: string) => void;
  /** When set, the token is handed to the caller instead of starting a web session. */
  onCredential?: (idToken: string) => void;
}) {
  const { loginWithGoogle } = useAuth();
  const navigate = useNavigate();
  const containerRef = useRef<HTMLDivElement>(null);
  const { viteGoogleClientId } = getWebEnv();

  useEffect(() => {
    if (!viteGoogleClientId || !containerRef.current) {
      return;
    }
    const container = containerRef.current;
    const render = () => {
      renderGoogleButton(container, viteGoogleClientId, (idToken) => {
        if (onCredential) {
          onCredential(idToken);
          return;
        }
        loginWithGoogle(idToken)
          .then(() => navigate("/leghe"))
          .catch((error: unknown) => {
            onError(getApiErrorMessage(error, "Accesso con Google non riuscito."));
          });
      }).catch(() => {
        onError("Impossibile caricare l'accesso con Google.");
      });
    };
    render();
    // Il bottone è un iframe di Google: al cambio tema va ridisegnato con il tema giusto.
    const observer = new MutationObserver(render);
    observer.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ["data-color-scheme"],
    });
    return () => observer.disconnect();
  }, [viteGoogleClientId, loginWithGoogle, navigate, onError, onCredential]);

  if (!viteGoogleClientId) {
    return null;
  }

  return (
    <div className="fa-auth-layout__google">
      <p className="fa-auth-layout__divider">oppure</p>
      <div ref={containerRef} className="fa-auth-layout__google-button" data-testid="auth-google-button" />
    </div>
  );
}

export function AuthRegisterPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);

    if (!email.trim() || !password || !displayName.trim()) {
      setError("Compila tutti i campi obbligatori.");
      return;
    }
    if (password !== confirmPassword) {
      setError("Le password non coincidono.");
      return;
    }

    setLoading(true);
    try {
      const response = await registerApi({ email, password, displayName });
      setSuccessMessage(response.message);
    } catch (submitError) {
      setError(getApiErrorMessage(submitError, "Registrazione non riuscita."));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="fa-auth-page fa-login" data-testid="register-page">
      <section className="fa-login__hero">
        <BrandLogo variant="full" size="lg" />
        <div className="fa-login__greeting">
          <h1 className="fa-login__title">
            Crea la tua <span className="fa-login__title-accent">squadra</span>
          </h1>
        </div>
        <ol className="fa-login__steps" aria-label="Come funziona">
          {REGISTER_STEPS.map((step, index) => (
            <li key={step.title} className="fa-login__step">
              <span className="fa-login__step-n" aria-hidden="true">
                {index + 1}
              </span>
              <span>
                <strong>{step.title}</strong>
                <small>{step.detail}</small>
              </span>
            </li>
          ))}
        </ol>
      </section>
      <section className="fa-login__panel">
        {successMessage ? (
          <>
            <UiStatePanel
              state="success"
              title="Controlla la tua email"
              message={successMessage}
              testId="auth-register-success"
            />
            <p className="fa-auth-layout__register">
              <Link to="/accedi">Torna al login</Link>
            </p>
          </>
        ) : (
          <>
            <AuthFormLayout
              brand={null}
              hideBrand
              title="Registrati"
              submitLabel="Crea account"
              showDisplayName
              showConfirmPassword
              email={email}
              password={password}
              confirmPassword={confirmPassword}
              displayName={displayName}
              onEmailChange={setEmail}
              onPasswordChange={setPassword}
              onConfirmPasswordChange={setConfirmPassword}
              onDisplayNameChange={setDisplayName}
              onSubmit={handleSubmit}
              loading={loading}
              error={error ?? undefined}
              registerPrompt={
                <p className="fa-auth-layout__register">
                  Hai già un account? <Link to="/accedi">Accedi</Link>
                </p>
              }
            />
            <GoogleSignInButton onError={setError} />
          </>
        )}
      </section>
    </div>
  );
}

const REGISTER_STEPS = [
  { title: "Crea l'account", detail: "Nome, email e password" },
  { title: "Conferma l'email", detail: "Ti scriviamo un codice" },
  { title: "Entra in lega", detail: "Crea la tua o usa un invito" },
] as const;

const LOGIN_ROLES = [
  { code: "P", label: "Portieri" },
  { code: "D", label: "Difensori" },
  { code: "C", label: "Centrocampisti" },
  { code: "A", label: "Attaccanti" },
] as const;

export function AuthLoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const { search } = useLocation();
  const [remembered, setRemembered] = useState<LastUser | null>(() => readLastUser());
  const [email, setEmail] = useState(() => readLastUser()?.email ?? "");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await login(email, password);
      const sessionUser = loadStoredSession()?.user;
      if (sessionUser?.displayName && email.trim()) {
        writeLastUser({ displayName: sessionUser.displayName, email: email.trim() });
      }
      const params = new URLSearchParams(search);
      const returnTo = params.get("returnTo");
      navigate(returnTo ? decodeURIComponent(returnTo) : "/leghe");
    } catch (submitError) {
      setError(getApiErrorMessage(submitError, "Accesso non riuscito."));
    } finally {
      setLoading(false);
    }
  }

  function switchAccount() {
    clearLastUser();
    setRemembered(null);
    setEmail("");
    setPassword("");
    setError(null);
  }

  const firstName = remembered?.displayName.trim().split(/\s+/)[0] ?? "";

  return (
    <div className="fa-auth-page fa-login" data-testid="login-page">
      <section className="fa-login__hero">
        <BrandLogo variant="full" size="lg" />
        {remembered ? (
          <div className="fa-login__greeting" data-testid="login-greeting">
            <div className="fa-login__avatar" aria-hidden="true">
              <div className="fa-login__avatar-kit">
                <span className="fa-login__avatar-initials">{initialsOf(remembered.displayName)}</span>
              </div>
            </div>
            <h1 className="fa-login__title">
              Bentornato,
              <br />
              <span className="fa-login__title-accent">{firstName}</span>
            </h1>
          </div>
        ) : (
          <div className="fa-login__greeting">
            <h1 className="fa-login__title">
              Il fantacalcio che si{" "}
              <span className="fa-login__title-accent">gioca davvero</span>
            </h1>
          </div>
        )}
        <ul className="fa-login__roles" aria-label="Ruoli">
          {LOGIN_ROLES.map((role) => (
            <li
              key={role.code}
              className={`fa-login__role fa-login__role--${role.code.toLowerCase()}`}
              title={role.label}
            >
              {role.code}
            </li>
          ))}
        </ul>
      </section>
      <section className="fa-login__panel">
        <AuthFormLayout
          brand={null}
          hideBrand
          title="Accedi"
          submitLabel={remembered ? `Accedi come ${firstName}` : "Accedi"}
          email={email}
          password={password}
          onEmailChange={setEmail}
          onPasswordChange={setPassword}
          onSubmit={handleSubmit}
          loading={loading}
          error={error ?? undefined}
          emailSlot={
            remembered ? (
              <div className="fa-login__account" data-testid="login-remembered-account">
                <div>
                  <span className="fa-login__account-label">Account</span>
                  <strong className="fa-login__account-email">{remembered.email}</strong>
                </div>
                <button type="button" className="fa-login__account-switch" onClick={switchAccount}>
                  Cambia
                </button>
              </div>
            ) : undefined
          }
          forgotPasswordLink={
            <p className="fa-auth-layout__forgot">
              <Link to="/accedi/recupera">Password dimenticata?</Link>
            </p>
          }
          registerPrompt={
            <p className="fa-auth-layout__register">
              {remembered ? (
                <>
                  <button type="button" className="fa-login__account-switch" onClick={switchAccount}>
                    Non sei {firstName}? Cambia account
                  </button>
                  <br />
                </>
              ) : null}
              Non hai un account? <Link to="/accedi/registrati">Registrati</Link>
            </p>
          }
        />
        <GoogleSignInButton onError={setError} />
      </section>
    </div>
  );
}

/** Shown after Google returns a credential, when the app did not open by itself. */
export function GoogleAppHandoffLink({ href }: { href: string }) {
  return (
    <div className="fa-auth-layout__google">
      <p>L'app dovrebbe aprirsi. Se resti qui, tocca il pulsante.</p>
      <a className="fa-btn fa-btn--primary" href={href} style={{ textDecoration: "none" }}>
        Apri FantApperò
      </a>
    </div>
  );
}

/** Mobile handoff: Google button on this origin, then return the ID token to the app. */
export function AuthGoogleAppPage() {
  const { search } = useLocation();
  const returnTo = googleAppReturnUrl(new URLSearchParams(search).get("return"));
  const [error, setError] = useState<string | null>(null);
  const [handoffUrl, setHandoffUrl] = useState<string | null>(null);
  const handoff = useCallback(
    (idToken: string) => {
      if (!returnTo) {
        return;
      }
      const next = googleAppHandoffUrl(returnTo, idToken);
      setHandoffUrl(next);
      window.location.replace(next);
    },
    [returnTo],
  );

  return (
    <div className="fa-auth-page fa-surface-pitch">
      <PageContainer title="Accedi">
        {returnTo ? (
          <>
            <p>Continua con Google per tornare all'app.</p>
            {error ? (
              <UiStatePanel state="error" title="Accesso non riuscito" message={error} />
            ) : null}
            {handoffUrl ? (
              <GoogleAppHandoffLink href={handoffUrl} />
            ) : (
              <GoogleSignInButton onError={setError} onCredential={handoff} />
            )}
          </>
        ) : (
          <UiStatePanel
            state="error"
            title="Collegamento non valido"
            message="Apri di nuovo «Continua con Google» dall'app."
          />
        )}
      </PageContainer>
    </div>
  );
}

export function AuthForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const response = await forgotPassword({ email });
      setSuccessMessage(response.message);
    } catch (submitError) {
      setError(getApiErrorMessage(submitError, "Richiesta non riuscita."));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="fa-auth-page fa-surface-pitch">
      <PageContainer title="Recupera accesso">
        {successMessage ? (
          <UiStatePanel
            state="success"
            title="Controlla la tua email"
            message={successMessage}
            testId="auth-forgot-success"
          />
        ) : (
          <AuthFormLayout
            brand={<BrandLogo variant="full" size="lg" />}
            title="Password dimenticata"
            submitLabel="Invia link di reset"
            showPassword={false}
            email={email}
            onEmailChange={setEmail}
            onSubmit={handleSubmit}
            loading={loading}
            error={error ?? undefined}
            registerPrompt={
              <p className="fa-auth-layout__register">
                <Link to="/accedi">Torna al login</Link>
              </p>
            }
          />
        )}
      </PageContainer>
    </div>
  );
}

export function AuthResetPasswordPage() {
  const { search } = useLocation();
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const token = new URLSearchParams(search).get("token") ?? "";

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    if (!token) {
      setError("Link non valido. Richiedi un nuovo reset password.");
      return;
    }
    if (password !== confirmPassword) {
      setError("Le password non coincidono.");
      return;
    }
    setLoading(true);
    try {
      const response = await resetPassword({ token, newPassword: password });
      setSuccessMessage(response.message);
    } catch (submitError) {
      setError(getApiErrorMessage(submitError, "Reset password non riuscito."));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="fa-auth-page fa-surface-pitch">
      <PageContainer title="Reimposta password">
        {successMessage ? (
          <>
            <UiStatePanel
              state="success"
              title="Password aggiornata"
              message={successMessage}
              testId="auth-reset-success"
            />
            <p className="fa-auth-layout__register">
              <Link to="/accedi">Vai al login</Link>
            </p>
          </>
        ) : (
          <AuthFormLayout
            brand={<BrandLogo variant="full" size="lg" />}
            title="Scegli una nuova password"
            submitLabel="Salva password"
            showEmail={false}
            showConfirmPassword
            password={password}
            confirmPassword={confirmPassword}
            onPasswordChange={setPassword}
            onConfirmPasswordChange={setConfirmPassword}
            onSubmit={handleSubmit}
            loading={loading}
            error={error ?? undefined}
            registerPrompt={
              <p className="fa-auth-layout__register">
                <Link to="/accedi">Torna al login</Link>
              </p>
            }
          />
        )}
      </PageContainer>
    </div>
  );
}

export function AuthVerifyEmailPage() {
  const { search } = useLocation();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  // The verification token is single-use: React's StrictMode double-invokes
  // effects in development (mount → cleanup → mount again, without a real
  // unmount), which would otherwise send the token twice and show the
  // harmless-but-confusing second (already-used) failure instead of the real
  // first success. `requestedRef` makes sure the request itself only ever
  // fires once. `liveRef` tracks whether *some* instance of this effect is
  // currently mounted — unlike a `cancelled` variable captured per effect
  // invocation, it gets set back to `true` by the second (StrictMode) mount,
  // so the first invocation's still-pending promise is correctly allowed to
  // apply its result instead of being permanently silenced by the
  // synthetic cleanup that ran in between.
  const requestedRef = useRef(false);
  const liveRef = useRef(true);

  useEffect(() => {
    liveRef.current = true;
    return () => {
      liveRef.current = false;
    };
  }, []);

  useEffect(() => {
    const token = new URLSearchParams(search).get("token") ?? "";
    if (!token) {
      setError("Link di verifica non valido.");
      setLoading(false);
      return;
    }
    if (requestedRef.current) {
      return;
    }
    requestedRef.current = true;

    verifyEmail({ token })
      .then((response) => {
        if (liveRef.current) {
          setSuccessMessage(response.message);
        }
      })
      .catch((verifyError) => {
        if (liveRef.current) {
          setError(getApiErrorMessage(verifyError, "Verifica email non riuscita."));
        }
      })
      .finally(() => {
        if (liveRef.current) {
          setLoading(false);
        }
      });
  }, [search]);

  if (loading) {
    return (
      <div className="fa-auth-page fa-surface-pitch">
        <PageContainer title="Verifica email">
          <UiStatePanel
            state="loading"
            title="Verifica in corso"
            message="Stiamo confermando il tuo indirizzo email…"
            testId="auth-verify-loading"
          />
        </PageContainer>
      </div>
    );
  }

  return (
    <div className="fa-auth-page fa-surface-pitch">
      <PageContainer title="Verifica email">
        {successMessage ? (
          <>
            <UiStatePanel
              state="success"
              title="Email verificata"
              message={successMessage}
              testId="auth-verify-success"
            />
            <p className="fa-auth-layout__register">
              <Link to="/accedi">Accedi ora</Link>
            </p>
          </>
        ) : (
          <UiStatePanel
            state="error"
            title="Verifica non riuscita"
            message={error ?? "Link non valido o scaduto."}
            testId="auth-verify-error"
          />
        )}
      </PageContainer>
    </div>
  );
}
