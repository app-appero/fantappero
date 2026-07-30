import type { Permission } from "@fantappero/contracts";
import { UiStatePanel } from "@fantappero/ui";
import { type ReactNode } from "react";
import { useAuth } from "../auth/AuthContext";

export type RequirePermissionsProps = {
  required: readonly Permission[];
  children: ReactNode;
};

/** Client-side gate — server remains authoritative (EP02-03). */
export function RequirePermissions({ required, children }: RequirePermissionsProps) {
  const { can } = useAuth();

  if (!can(required)) {
    return (
      <UiStatePanel
        state="forbidden"
        title="Permessi insufficienti"
        message="Non hai accesso a questa sezione. Contatta l'amministratore di lega se pensi sia un errore."
        testId="route-forbidden"
      />
    );
  }

  return <>{children}</>;
}

export type RequireGlobalOperatorProps = {
  children: ReactNode;
};

export function RequireGlobalOperator({ children }: RequireGlobalOperatorProps) {
  const { user } = useAuth();

  if (user.globalRole !== "global_operator") {
    return (
      <UiStatePanel
        state="forbidden"
        title="Area riservata"
        message="Il pannello operatore globale è accessibile solo allo staff piattaforma."
        testId="route-forbidden"
      />
    );
  }

  return <>{children}</>;
}
