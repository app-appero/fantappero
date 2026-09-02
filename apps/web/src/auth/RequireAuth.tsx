import { UiStatePanel } from "@fantappero/ui";
import { type ReactNode, useEffect } from "react";
import { useAuth } from "./AuthContext";
import { useLocation, useNavigate } from "../router/simpleRouter";

export type RequireAuthProps = {
  children: ReactNode;
};

/** Redirect unauthenticated users to login (EP02-01). Demo persona bypasses in dev. */
export function RequireAuth({ children }: RequireAuthProps) {
  const { isAuthenticated, isDemoMode, loading } = useAuth();
  const navigate = useNavigate();
  const { pathname, search } = useLocation();

  useEffect(() => {
    if (!loading && !isAuthenticated && !isDemoMode) {
      const returnTo = encodeURIComponent(`${pathname}${search}`);
      navigate(`/accedi?returnTo=${returnTo}`, { replace: true });
    }
  }, [isAuthenticated, isDemoMode, loading, navigate, pathname, search]);

  if (loading) {
    return (
      <UiStatePanel
        state="loading"
        title="Caricamento sessione"
        message="Stiamo verificando le tue credenziali…"
        testId="auth-loading"
      />
    );
  }

  if (!isAuthenticated && !isDemoMode) {
    return (
      <UiStatePanel
        state="loading"
        title="Reindirizzamento"
        message="Ti stiamo portando alla pagina di accesso…"
        testId="auth-redirect"
      />
    );
  }

  return <>{children}</>;
}
