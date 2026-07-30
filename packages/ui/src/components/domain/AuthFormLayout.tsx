import { type ReactNode } from "react";
import { Button } from "../Button.js";
import { Card, CardBody, CardFooter, CardHeader } from "../Card.js";
import { Input } from "../Input.js";

export type AuthFormLayoutProps = {
  brand: ReactNode;
  title: string;
  emailLabel: string;
  emailPlaceholder: string;
  passwordLabel: string;
  passwordPlaceholder: string;
  submitLabel: string;
  forgotPasswordLabel?: string;
  registerPrompt?: ReactNode;
  testId?: string;
};

/** Presentational auth form shell — no auth logic (EPUI-04 wireframe). */
export function AuthFormLayout({
  brand,
  title,
  emailLabel,
  emailPlaceholder,
  passwordLabel,
  passwordPlaceholder,
  submitLabel,
  forgotPasswordLabel,
  registerPrompt,
  testId = "auth-form-layout",
}: AuthFormLayoutProps) {
  return (
    <div className="fa-auth-layout" data-testid={testId}>
      <div className="fa-auth-layout__brand">{brand}</div>
      <Card>
        <CardHeader>{title}</CardHeader>
        <CardBody>
          <Input
            label={emailLabel}
            placeholder={emailPlaceholder}
            name="email"
            type="email"
            autoComplete="email"
          />
          <Input
            label={passwordLabel}
            placeholder={passwordPlaceholder}
            name="password"
            type="password"
            autoComplete="current-password"
          />
          {forgotPasswordLabel ? (
            <p className="fa-auth-layout__forgot">
              <a href="/accedi/recupera">{forgotPasswordLabel}</a>
            </p>
          ) : null}
        </CardBody>
        <CardFooter>
          <Button variant="primary" type="submit">
            {submitLabel}
          </Button>
          {registerPrompt}
        </CardFooter>
      </Card>
    </div>
  );
}
