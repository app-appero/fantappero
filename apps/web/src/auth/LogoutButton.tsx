import { useState } from "react";
import { useNavigate } from "../router/simpleRouter";
import { useAuth } from "./AuthContext";

/** Termina la sessione e torna al login (EP02-01). */
export function LogoutButton() {
  const { logout, isDemoMode } = useAuth();
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);

  async function handleLogout() {
    setLoading(true);
    try {
      if (!isDemoMode) {
        await logout();
      }
      navigate("/accedi", { replace: true });
    } finally {
      setLoading(false);
    }
  }

  return (
    <button
      type="button"
      className="fa-link-muted fa-logout-button"
      onClick={() => void handleLogout()}
      disabled={loading}
      data-testid="logout-button"
    >
      {loading ? "Uscita…" : "Esci"}
    </button>
  );
}
