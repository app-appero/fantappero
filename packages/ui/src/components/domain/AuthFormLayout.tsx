import { type FormEvent, type ReactNode } from "react";
import { Button } from "../Button.js";
import { Card, CardBody, CardFooter, CardHeader } from "../Card.js";
import { Input } from "../Input.js";

export type AuthFormLayoutProps = {
  brand: ReactNode;
  title: string;
  submitLabel: string;
  testId?: string;
  emailLabel?: string;
  emailPlaceholder?: string;
  passwordLabel?: string;
  passwordPlaceholder?: string;
  confirmPasswordLabel?: string;
  confirmPasswordPlaceholder?: string;
  displayNameLabel?: string;
  displayNamePlaceholder?: string;
  forgotPasswordLabel?: string;
  forgotPasswordLink?: ReactNode;
  registerPrompt?: ReactNode;
  showEmail?: boolean;
  showPassword?: boolean;
  showConfirmPassword?: boolean;
  showDisplayName?: boolean;
  loading?: boolean;
  error?: string;
  email?: string;
  password?: string;
  confirmPassword?: string;
  displayName?: string;
  onEmailChange?: (value: string) => void;
  onPasswordChange?: (value: string) => void;
  onConfirmPasswordChange?: (value: string) => void;
  onDisplayNameChange?: (value: string) => void;
  onSubmit?: (event: FormEvent<HTMLFormElement>) => void;
};

/** Presentational auth form shell — optional controlled fields and submit handler. */
export function AuthFormLayout({
  brand,
  title,
  emailLabel = "Email",
  emailPlaceholder = "nome@esempio.it",
  passwordLabel = "Password",
  passwordPlaceholder = "••••••••",
  confirmPasswordLabel = "Conferma password",
  confirmPasswordPlaceholder = "••••••••",
  displayNameLabel = "Nome visualizzato",
  displayNamePlaceholder = "Il tuo nome",
  submitLabel,
  forgotPasswordLabel,
  forgotPasswordLink,
  registerPrompt,
  testId = "auth-form-layout",
  showEmail = true,
  showPassword = true,
  showConfirmPassword = false,
  showDisplayName = false,
  loading = false,
  error,
  email = "",
  password = "",
  confirmPassword = "",
  displayName = "",
  onEmailChange,
  onPasswordChange,
  onConfirmPasswordChange,
  onDisplayNameChange,
  onSubmit,
}: AuthFormLayoutProps) {
  const forgotLink =
    forgotPasswordLink ??
    (forgotPasswordLabel ? (
      <p className="fa-auth-layout__forgot">
        <a href="/accedi/recupera">{forgotPasswordLabel}</a>
      </p>
    ) : null);

  return (
    <form className="fa-auth-layout" data-testid={testId} onSubmit={onSubmit} noValidate>
      <div className="fa-auth-layout__brand">{brand}</div>
      <Card>
        <CardHeader>{title}</CardHeader>
        <CardBody>
          {error ? (
            <p className="fa-field__error" role="alert" data-testid="auth-form-error">
              {error}
            </p>
          ) : null}
          {showDisplayName ? (
            <Input
              label={displayNameLabel}
              placeholder={displayNamePlaceholder}
              name="displayName"
              type="text"
              autoComplete="name"
              value={displayName}
              onChange={(event) => onDisplayNameChange?.(event.target.value)}
              disabled={loading}
              required
            />
          ) : null}
          {showEmail ? (
            <Input
              label={emailLabel}
              placeholder={emailPlaceholder}
              name="email"
              type="email"
              autoComplete="email"
              value={email}
              onChange={(event) => onEmailChange?.(event.target.value)}
              disabled={loading}
              required
            />
          ) : null}
          {showPassword ? (
            <Input
              label={passwordLabel}
              placeholder={passwordPlaceholder}
              name="password"
              type="password"
              autoComplete={showConfirmPassword ? "new-password" : "current-password"}
              value={password}
              onChange={(event) => onPasswordChange?.(event.target.value)}
              disabled={loading}
              required
            />
          ) : null}
          {showConfirmPassword ? (
            <Input
              label={confirmPasswordLabel}
              placeholder={confirmPasswordPlaceholder}
              name="confirmPassword"
              type="password"
              autoComplete="new-password"
              value={confirmPassword}
              onChange={(event) => onConfirmPasswordChange?.(event.target.value)}
              disabled={loading}
              required
            />
          ) : null}
          {forgotLink}
        </CardBody>
        <CardFooter>
          <Button variant="primary" type="submit" disabled={loading}>
            {loading ? "Attendere…" : submitLabel}
          </Button>
          {registerPrompt}
        </CardFooter>
      </Card>
    </form>
  );
}
