import { Button } from "@fantappero/ui";
import { useState } from "react";
import { useNavigate } from "../router/simpleRouter";
import { useAuth } from "./AuthContext";

/** Banner fisso durante un'impersonificazione di supporto (EP11-impersonation). */
export function ImpersonationBanner() {
  const { user, stopImpersonation } = useAuth();
  const navigate = useNavigate();
  const [working, setWorking] = useState(false);

  async function handleExit() {
    setWorking(true);
    try {
      await stopImpersonation();
      navigate("/admin/utenti");
    } finally {
      setWorking(false);
    }
  }

  return (
    <div className="fa-impersonation-banner" role="status" data-testid="impersonation-banner">
      <span>
        Stai impersonando <strong>{user?.displayName ?? "un utente"}</strong> a scopo di
        assistenza.
      </span>
      <Button
        type="button"
        size="sm"
        variant="secondary"
        loading={working}
        onClick={() => void handleExit()}
        data-testid="impersonation-exit"
      >
        Torna al tuo account
      </Button>
    </div>
  );
}
