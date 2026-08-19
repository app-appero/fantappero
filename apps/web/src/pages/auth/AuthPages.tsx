import { AuthFormLayout, BrandLogo, PageContainer, UiStatePanel } from "@fantappero/ui";
import { type FormEvent, useEffect, useState } from "react";
import {
  forgotPassword,
  register as registerApi,
  resetPassword,
  verifyEmail,
} from "../../api/auth";
import { getApiErrorMessage, useAuth } from "../../auth/AuthContext";
import { Link, useLocation, useNavigate } from "../../router/simpleRouter";

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
    <div className="fa-auth-page fa-surface-pitch">
      <PageContainer title="Registrati">
        {successMessage ? (
          <UiStatePanel
            state="success"
            title="Controlla la tua email"
            message={successMessage}
            testId="auth-register-success"
          />
        ) : (
          <AuthFormLayout
            brand={<BrandLogo variant="full" size="lg" />}
            title="Crea account"
            submitLabel="Registrati"
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
        )}
        {successMessage ? (
          <p className="fa-auth-layout__register">
            <Link to="/accedi">Torna al login</Link>
          </p>
        ) : null}
      </PageContainer>
    </div>
  );
}

export function AuthLoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const { search } = useLocation();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await login(email, password);
      const params = new URLSearchParams(search);
      const returnTo = params.get("returnTo");
      navigate(returnTo ? decodeURIComponent(returnTo) : "/leghe");
    } catch (submitError) {
      setError(getApiErrorMessage(submitError, "Accesso non riuscito."));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="fa-auth-page fa-surface-pitch">
      <PageContainer title="Accedi">
        <AuthFormLayout
          brand={<BrandLogo variant="full" size="lg" />}
          title="Accedi al tuo account"
          submitLabel="Accedi"
          email={email}
          password={password}
          onEmailChange={setEmail}
          onPasswordChange={setPassword}
          onSubmit={handleSubmit}
          loading={loading}
          error={error ?? undefined}
          forgotPasswordLink={
            <p className="fa-auth-layout__forgot">
              <Link to="/accedi/recupera">Password dimenticata?</Link>
            </p>
          }
          registerPrompt={
            <p className="fa-auth-layout__register">
              Non hai un account? <Link to="/accedi/registrati">Registrati</Link>
            </p>
          }
        />
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

  useEffect(() => {
    const token = new URLSearchParams(search).get("token") ?? "";
    if (!token) {
      setError("Link di verifica non valido.");
      setLoading(false);
      return;
    }

    let cancelled = false;
    verifyEmail({ token })
      .then((response) => {
        if (!cancelled) {
          setSuccessMessage(response.message);
        }
      })
      .catch((verifyError) => {
        if (!cancelled) {
          setError(getApiErrorMessage(verifyError, "Verifica email non riuscita."));
        }
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
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
