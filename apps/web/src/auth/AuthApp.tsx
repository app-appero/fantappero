import { useCallback, useEffect, useMemo, useState, type CSSProperties, type FormEvent, type ReactNode } from "react";
import {
  type AsyncState,
  type AuthFormState,
  type AuthView,
  DEFAULT_UI_LOCALE,
  SUPPORTED_LANGUAGES,
  type SupportedLanguage,
  type UserProfileResponse,
  ui,
} from "@fantappero/contracts";
import { colors, spacing, typography } from "@fantappero/ui";
import {
  AUTH_TOKEN_STORAGE_KEY,
  AuthApiError,
  createAuthClient,
  type AuthClient,
} from "../api/auth";
import { getApiBaseUrl } from "../config/env";
import { createLeagueClient } from "../api/leagues";
import { CreateLeaguePanel } from "../leagues/CreateLeaguePanel";
import { ProfilePanel } from "../profile/ProfilePanel";
import { PrivacyPanel } from "../profile/PrivacyPanel";

const initialFormState: AuthFormState = { status: "idle" };

function resolveLocale(language?: string): SupportedLanguage {
  if (language && SUPPORTED_LANGUAGES.includes(language as SupportedLanguage)) {
    return language as SupportedLanguage;
  }
  return DEFAULT_UI_LOCALE;
}

function readStoredToken(): string | null {
  if (typeof window === "undefined") {
    return null;
  }
  return window.localStorage.getItem(AUTH_TOKEN_STORAGE_KEY);
}

function storeToken(token: string | null) {
  if (typeof window === "undefined") {
    return;
  }
  if (token) {
    window.localStorage.setItem(AUTH_TOKEN_STORAGE_KEY, token);
  } else {
    window.localStorage.removeItem(AUTH_TOKEN_STORAGE_KEY);
  }
}

function fieldStyle(): CSSProperties {
  return {
    width: "100%",
    padding: spacing.sm,
    borderRadius: 8,
    border: `1px solid ${colors.muted}`,
    background: colors.background,
    color: colors.foreground,
    fontFamily: typography.fontFamily,
    fontSize: typography.fontSize.md,
    boxSizing: "border-box",
  };
}

function buttonStyle(disabled: boolean): CSSProperties {
  return {
    marginTop: spacing.sm,
    padding: `${spacing.sm}px ${spacing.md}px`,
    borderRadius: 8,
    border: "none",
    background: disabled ? colors.muted : colors.ok,
    color: colors.background,
    fontWeight: 600,
    cursor: disabled ? "not-allowed" : "pointer",
    fontFamily: typography.fontFamily,
  };
}

function statusBanner(state: AuthFormState, copy: ReturnType<typeof ui>): ReactNode {
  if (state.status === "loading") {
    return (
      <p data-testid="auth-status" style={{ color: colors.muted }}>
        {copy.loading}
      </p>
    );
  }
  if (state.status === "error" && state.error) {
    return (
      <p data-testid="auth-error" style={{ color: "#f87171" }}>
        {state.error.message}
      </p>
    );
  }
  if (state.status === "success" && state.message) {
    return (
      <p data-testid="auth-success" style={{ color: colors.ok }}>
        {state.message}
      </p>
    );
  }
  if (state.status === "empty") {
    return (
      <p data-testid="auth-empty" style={{ color: colors.muted }}>
        {copy.fillForm}
      </p>
    );
  }
  return null;
}

export interface AuthAppProps {
  client?: AuthClient;
  initialView?: AuthView;
  initialToken?: string | null;
  initialUser?: UserProfileResponse | null;
}

export function AuthApp({
  client: clientOverride,
  initialView = "login",
  initialToken = null,
  initialUser = null,
}: AuthAppProps) {
  const client = useMemo(
    () => clientOverride ?? createAuthClient(getApiBaseUrl()),
    [clientOverride],
  );
  const leagueClient = useMemo(() => createLeagueClient(getApiBaseUrl()), []);

  const [view, setView] = useState<AuthView>(initialView);
  const [token, setToken] = useState<string | null>(initialToken ?? readStoredToken());
  const [user, setUser] = useState<UserProfileResponse | null>(initialUser);
  const [form, setForm] = useState(initialFormState);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [resetToken, setResetToken] = useState("");
  const [newPassword, setNewPassword] = useState("");

  const copy = ui(resolveLocale(user?.language));

  const loadAccount = useCallback(async () => {
    if (!token) {
      setUser(null);
      setView("login");
      setForm({ status: "empty" });
      return;
    }
    setForm({ status: "loading" });
    try {
      const profile = await client.me(token);
      setUser(profile);
      setView("account");
      setForm({ status: "success", message: ui(resolveLocale(profile.language)).signedIn });
    } catch (error) {
      storeToken(null);
      setToken(null);
      setUser(null);
      setView("login");
      if (error instanceof AuthApiError) {
        setForm({ status: "error", error: { code: error.code, message: error.message } });
      } else {
        setForm({
          status: "error",
          error: { code: "network_error", message: copy.networkError },
        });
      }
    }
  }, [client, token]);

  useEffect(() => {
    if (token && !user && view !== "verify-email" && view !== "reset-password") {
      void loadAccount();
    }
  }, [token, user, view, loadAccount]);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (!email.trim() || !password.trim()) {
      setForm({ status: "empty" });
      return;
    }
    setForm({ status: "loading" });
    try {
      const session =
        view === "register"
          ? await client.register(email.trim(), password)
          : await client.login(email.trim(), password);
      storeToken(session.access_token);
      setToken(session.access_token);
      const profile = await client.me(session.access_token);
      setUser(profile);
      setView("account");
      setForm({
        status: "success",
        message: view === "register" ? copy.accountCreated : copy.welcomeBack,
      });
    } catch (error) {
      if (error instanceof AuthApiError) {
        setForm({ status: "error", error: { code: error.code, message: error.message } });
      } else {
        setForm({
          status: "error",
          error: { code: "network_error", message: copy.networkError },
        });
      }
    }
  }

  async function handleForgotPassword(event: FormEvent) {
    event.preventDefault();
    if (!email.trim()) {
      setForm({ status: "empty" });
      return;
    }
    setForm({ status: "loading" });
    try {
      const response = await client.requestPasswordReset(email.trim());
      setForm({ status: "success", message: response.message });
    } catch (error) {
      if (error instanceof AuthApiError) {
        setForm({ status: "error", error: { code: error.code, message: error.message } });
      } else {
        setForm({
          status: "error",
          error: { code: "network_error", message: copy.networkError },
        });
      }
    }
  }

  async function handleResetPassword(event: FormEvent) {
    event.preventDefault();
    if (!resetToken.trim() || !newPassword.trim()) {
      setForm({ status: "empty" });
      return;
    }
    setForm({ status: "loading" });
    try {
      const response = await client.resetPassword(resetToken.trim(), newPassword);
      setForm({ status: "success", message: response.message });
      setView("login");
    } catch (error) {
      if (error instanceof AuthApiError) {
        setForm({ status: "error", error: { code: error.code, message: error.message } });
      } else {
        setForm({
          status: "error",
          error: { code: "network_error", message: copy.networkError },
        });
      }
    }
  }

  async function handleVerifyEmail(event: FormEvent) {
    event.preventDefault();
    if (!resetToken.trim()) {
      setForm({ status: "empty" });
      return;
    }
    setForm({ status: "loading" });
    try {
      const profile = await client.verifyEmail(resetToken.trim());
      setUser(profile);
      setView("account");
      setForm({ status: "success", message: copy.emailVerified });
    } catch (error) {
      if (error instanceof AuthApiError) {
        setForm({ status: "error", error: { code: error.code, message: error.message } });
      } else {
        setForm({
          status: "error",
          error: { code: "network_error", message: copy.networkError },
        });
      }
    }
  }

  async function handleLogout() {
    if (!token) {
      return;
    }
    setForm({ status: "loading" });
    try {
      await client.logout(token);
    } catch {
      // Clear local session even if revoke fails.
    }
    storeToken(null);
    setToken(null);
    setUser(null);
    setView("login");
    setForm({ status: "success", message: copy.loggedOut });
  }

  return (
    <main
      style={{
        minHeight: "100vh",
        margin: 0,
        padding: spacing.xl,
        background: `radial-gradient(circle at top left, #1c2736, ${colors.background})`,
        color: colors.foreground,
        fontFamily: typography.fontFamily,
      }}
    >
      <p
        style={{
          margin: 0,
          letterSpacing: "0.08em",
          textTransform: "uppercase",
          color: colors.muted,
          fontSize: typography.fontSize.sm,
        }}
      >
        FantApperò
      </p>
      <h1 style={{ margin: `${spacing.md}px 0`, fontSize: typography.fontSize.xl }}>
        {view === "profile"
          ? copy.profileTitle
          : view === "privacy"
            ? copy.privacyTitle
            : view === "create-league"
              ? copy.createLeagueTitle
            : view === "account"
              ? copy.accountTitle
              : copy.signInTitle}
      </h1>

      {statusBanner(form, copy)}

      {view === "account" && user ? (
        <section data-testid="account-panel">
          <dl style={{ display: "grid", gap: spacing.sm }}>
            <div>
              <dt style={{ color: colors.muted }}>{copy.email}</dt>
              <dd style={{ margin: 0 }} data-testid="account-email">
                {user.email}
              </dd>
            </div>
            <div>
              <dt style={{ color: colors.muted }}>{copy.name}</dt>
              <dd style={{ margin: 0 }} data-testid="account-display-name">
                {user.display_name ?? "—"}
              </dd>
            </div>
            <div>
              <dt style={{ color: colors.muted }}>{copy.verified}</dt>
              <dd style={{ margin: 0 }} data-testid="account-verified">
                {user.email_verified ? copy.yes : copy.no}
              </dd>
            </div>
          </dl>
          {!user.email_verified ? (
            <p data-testid="account-verify-required" style={{ color: "#fbbf24", marginBottom: spacing.sm }}>
              {copy.emailNotVerified}
            </p>
          ) : null}
          <button
            type="button"
            style={buttonStyle(false)}
            data-testid="account-edit-profile"
            onClick={() => setView("profile")}
          >
            {copy.editProfile}
          </button>
          {!user.email_verified ? (
            <button
              type="button"
              style={buttonStyle(false)}
              data-testid="account-verify-email"
              onClick={() => setView("verify-email")}
            >
              {copy.goVerifyEmail}
            </button>
          ) : null}
          <button
            type="button"
            style={buttonStyle(user.email_verified ? false : true)}
            data-testid="account-create-league"
            onClick={() => setView("create-league")}
            disabled={!user.email_verified}
            title={!user.email_verified ? copy.emailNotVerified : undefined}
          >
            {copy.createLeagueLink}
          </button>
          <button
            type="button"
            style={buttonStyle(false)}
            data-testid="account-privacy"
            onClick={() => setView("privacy")}
          >
            {copy.privacyAndData}
          </button>
          <button type="button" style={buttonStyle(false)} onClick={() => void handleLogout()}>
            {copy.logOut}
          </button>
        </section>
      ) : null}

      {view === "profile" && user && token ? (
        <>
          <button type="button" style={buttonStyle(false)} onClick={() => setView("account")}>
            {copy.backToAccount}
          </button>
          <ProfilePanel
            client={client}
            token={token}
            profile={user}
            onUpdated={(updated) => setUser(updated)}
          />
        </>
      ) : null}

      {view === "privacy" && token ? (
        <>
          <button type="button" style={buttonStyle(false)} onClick={() => setView("account")}>
            {copy.backToAccount}
          </button>
          <PrivacyPanel
            client={client}
            token={token}
            onDeleted={() => {
              storeToken(null);
              setToken(null);
              setUser(null);
              setView("login");
              setForm({ status: "success", message: copy.accountDeleted });
            }}
          />
        </>
      ) : null}

      {view === "create-league" && token ? (
        <>
          <button type="button" style={buttonStyle(false)} onClick={() => setView("account")}>
            {copy.backToAccount}
          </button>
          <CreateLeaguePanel
            client={leagueClient}
            token={token}
            locale={resolveLocale(user?.language)}
            emailVerified={user?.email_verified ?? false}
            onVerifyEmail={() => setView("verify-email")}
            onCreated={() => setView("account")}
          />
        </>
      ) : null}

      {view === "login" || view === "register" ? (
        <form onSubmit={(event) => void handleSubmit(event)} style={{ maxWidth: 420 }}>
          <label style={{ display: "block", marginBottom: spacing.sm }}>
            {copy.email}
            <input
              data-testid="auth-email"
              type="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              style={fieldStyle()}
            />
          </label>
          <label style={{ display: "block", marginBottom: spacing.sm }}>
            {copy.password}
            <input
              data-testid="auth-password"
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              style={fieldStyle()}
            />
          </label>
          <button
            data-testid="auth-submit"
            type="submit"
            style={buttonStyle(form.status === "loading")}
            disabled={form.status === "loading"}
          >
            {view === "register" ? copy.createAccount : copy.signIn}
          </button>
          <p style={{ marginTop: spacing.md, color: colors.muted }}>
            {view === "login" ? (
              <button type="button" onClick={() => setView("register")}>
                {copy.needAccount}
              </button>
            ) : (
              <button type="button" onClick={() => setView("login")}>
                {copy.alreadyRegistered}
              </button>
            )}
            {" · "}
            <button type="button" onClick={() => setView("forgot-password")}>
              {copy.forgotPassword}
            </button>
          </p>
        </form>
      ) : null}

      {view === "forgot-password" ? (
        <form onSubmit={(event) => void handleForgotPassword(event)} style={{ maxWidth: 420 }}>
          <label style={{ display: "block", marginBottom: spacing.sm }}>
            {copy.email}
            <input
              data-testid="auth-email"
              type="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              style={fieldStyle()}
            />
          </label>
          <button type="submit" style={buttonStyle(form.status === "loading")}>
            {copy.sendResetLink}
          </button>
        </form>
      ) : null}

      {view === "reset-password" ? (
        <form onSubmit={(event) => void handleResetPassword(event)} style={{ maxWidth: 420 }}>
          <label style={{ display: "block", marginBottom: spacing.sm }}>
            {copy.resetToken}
            <input
              data-testid="auth-reset-token"
              value={resetToken}
              onChange={(event) => setResetToken(event.target.value)}
              style={fieldStyle()}
            />
          </label>
          <label style={{ display: "block", marginBottom: spacing.sm }}>
            {copy.newPassword}
            <input
              data-testid="auth-new-password"
              type="password"
              value={newPassword}
              onChange={(event) => setNewPassword(event.target.value)}
              style={fieldStyle()}
            />
          </label>
          <button type="submit" style={buttonStyle(form.status === "loading")}>
            {copy.updatePassword}
          </button>
        </form>
      ) : null}

      {view === "verify-email" ? (
        <form onSubmit={(event) => void handleVerifyEmail(event)} style={{ maxWidth: 420 }}>
          <label style={{ display: "block", marginBottom: spacing.sm }}>
            {copy.verificationToken}
            <input
              data-testid="auth-verify-token"
              value={resetToken}
              onChange={(event) => setResetToken(event.target.value)}
              style={fieldStyle()}
            />
          </label>
          <button type="submit" style={buttonStyle(form.status === "loading")}>
            {copy.verifyEmail}
          </button>
        </form>
      ) : null}
    </main>
  );
}

export function resolveInitialAuthView(search: string): AuthView {
  const params = new URLSearchParams(search);
  if (params.get("token") && params.get("mode") === "reset") {
    return "reset-password";
  }
  if (params.get("token")) {
    return "verify-email";
  }
  return "login";
}

export type { AsyncState, AuthFormState };
