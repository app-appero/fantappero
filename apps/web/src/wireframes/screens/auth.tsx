import { AuthFormLayout, BrandLogo, PageContainer } from "@fantappero/ui";
import { Link } from "../../router/simpleRouter";
import { WireframePage } from "../WireframePage";

export function AuthWireframePage() {
  return (
    <div className="fa-auth-page fa-surface-pitch">
      <PageContainer title="Accedi">
        <WireframePage
          screenId="auth"
          showMeta
          successContent={
            <AuthFormLayout
              brand={<BrandLogo variant="full" size="lg" />}
              title="Accedi al tuo account"
              emailLabel="Email"
              emailPlaceholder="nome@esempio.it"
              passwordLabel="Password"
              passwordPlaceholder="••••••••"
              submitLabel="Accedi"
              forgotPasswordLabel="Password dimenticata?"
              registerPrompt={
                <p className="fa-auth-layout__register">
                  Non hai un account? <Link to="/accedi/registrati">Registrati</Link>
                </p>
              }
            />
          }
        />
        <p className="fa-wireframe-note">
          Wireframe EPUI-04 — autenticazione reale in EP02-01.
        </p>
      </PageContainer>
    </div>
  );
}

export function AuthRegisterWireframePage() {
  return (
    <div className="fa-auth-page fa-surface-pitch">
      <PageContainer title="Registrati">
        <WireframePage
          screenId="auth"
          successContent={
            <AuthFormLayout
              brand={<BrandLogo variant="full" size="lg" />}
              title="Crea account"
              emailLabel="Email"
              emailPlaceholder="nome@esempio.it"
              passwordLabel="Password"
              passwordPlaceholder="••••••••"
              submitLabel="Registrati"
            />
          }
        />
      </PageContainer>
    </div>
  );
}
