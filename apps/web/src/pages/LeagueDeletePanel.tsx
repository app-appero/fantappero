import type { LeagueState } from "@fantappero/contracts";
import { Button, UiStatePanel } from "@fantappero/ui";
import { useState } from "react";
import { deleteLeague } from "../api/leagues";
import { getApiErrorMessage, useAuth } from "../auth/AuthContext";
import { loadStoredSession } from "../auth/sessionStorage";
import { useNavigate } from "../router/simpleRouter";
import { isLeagueDeletable } from "./leagueDeleteHelpers";

type Props = {
  leagueId: string | null;
  state: LeagueState;
  leagueName: string;
  isDemoMode: boolean;
};

/** Hard-delete solo in bozza/configurazione iniziale (EP03-05-EXT). */
export function LeagueDeletePanel({ leagueId, state, leagueName, isDemoMode }: Props) {
  const { unregisterLeague } = useAuth();
  const navigate = useNavigate();
  const [confirmed, setConfirmed] = useState(false);
  const [working, setWorking] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  if (!isLeagueDeletable(state)) {
    return null;
  }

  async function onDelete() {
    setError(null);
    setSuccess(null);
    if (!confirmed) {
      setError("Conferma esplicitamente l'eliminazione spuntando la casella.");
      return;
    }
    if (isDemoMode) {
      setSuccess("Lega eliminata (demo).");
      return;
    }
    if (!leagueId) {
      setError("Seleziona una lega prima di eliminarla.");
      return;
    }
    const stored = loadStoredSession();
    if (!stored?.accessToken) {
      setError("Sessione non disponibile. Accedi di nuovo.");
      return;
    }
    setWorking(true);
    try {
      await deleteLeague(stored.accessToken, leagueId);
      unregisterLeague(leagueId);
      setSuccess("Lega eliminata definitivamente.");
      navigate("/leghe");
    } catch (caught) {
      setError(getApiErrorMessage(caught, "Impossibile eliminare la lega."));
    } finally {
      setWorking(false);
    }
  }

  return (
    <section className="fa-league-delete" data-testid="league-delete-panel">
      <h2>Elimina lega</h2>
      <p>
        Disponibile solo in bozza o configurazione iniziale. Dopo l&apos;avvio stagione usa
        &quot;Archivia lega&quot;. L&apos;operazione è definitiva.
      </p>
      <label>
        <input
          type="checkbox"
          checked={confirmed}
          data-testid="league-delete-confirm"
          onChange={(event) => setConfirmed(event.target.checked)}
        />{" "}
        Confermo di voler eliminare definitivamente «{leagueName}»
      </label>
      {error ? (
        <UiStatePanel
          state="error"
          title="Eliminazione non riuscita"
          message={error}
          testId="league-delete-error"
        />
      ) : null}
      {success ? (
        <UiStatePanel
          state="success"
          title="Lega eliminata"
          message={success}
          testId="league-delete-success"
        />
      ) : null}
      <div className="fa-ds-showcase__row" style={{ marginTop: "0.75rem" }}>
        <Button
          type="button"
          variant="danger"
          loading={working}
          disabled={!confirmed}
          data-testid="league-delete-submit"
          onClick={() => void onDelete()}
        >
          Elimina lega
        </Button>
      </div>
    </section>
  );
}
