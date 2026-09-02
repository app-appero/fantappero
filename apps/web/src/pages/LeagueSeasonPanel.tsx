import type { LeagueLifecycle, LeagueState } from "@fantappero/contracts";
import { Button, UiStatePanel } from "@fantappero/ui";
import { useState } from "react";
import { transitionLeagueState } from "../api/leagues";
import { getApiErrorMessage } from "../auth/AuthContext";
import { loadStoredSession } from "../auth/sessionStorage";

const STATE_LABELS: Record<LeagueState, string> = {
  draft: "Bozza",
  configuring: "Configurazione",
  auction: "Asta",
  active: "Attiva",
  concluded: "Conclusa",
  archived: "Archiviata",
};

const ACTION_LABELS: Record<LeagueState, string> = {
  draft: "Torna alla bozza",
  configuring: "Apri configurazione",
  auction: "Avvia asta",
  active: "Avvia stagione",
  concluded: "Concludi stagione",
  archived: "Archivia lega",
};

type Props = {
  leagueId: string | null;
  lifecycle: LeagueLifecycle;
  isDemoMode: boolean;
  search: string;
  onChange: (lifecycle: LeagueLifecycle) => void;
};

function requestedState(search: string): "loading" | "empty" | "error" | null {
  const value = new URLSearchParams(search).get("stagione");
  return value === "loading" || value === "empty" || value === "error" ? value : null;
}

export function LeagueSeasonPanel({
  leagueId,
  lifecycle,
  isDemoMode,
  search,
  onChange,
}: Props) {
  const demoState = isDemoMode ? requestedState(search) : null;
  const [working, setWorking] = useState<LeagueState | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  if (demoState === "loading") {
    return (
      <UiStatePanel
        state="loading"
        title="Caricamento stato stagione"
        message="Verifica dello stato e dei prerequisiti in corso…"
        testId="league-season-loading"
      />
    );
  }
  if (demoState === "error") {
    return (
      <UiStatePanel
        state="error"
        title="Stato stagione non disponibile"
        message="Non è stato possibile verificare i prerequisiti (demo)."
        testId="league-season-error"
      />
    );
  }
  if (demoState === "empty") {
    return (
      <UiStatePanel
        state="empty"
        title="Nessuna transizione disponibile"
        message="La lega non ha azioni di stagione disponibili."
        testId="league-season-empty"
      />
    );
  }

  async function transition(targetState: LeagueState) {
    setError(null);
    setSuccess(null);
    if (isDemoMode) {
      onChange({ state: targetState, allowedTransitions: [], blockers: [] });
      setSuccess(`Stato aggiornato: ${STATE_LABELS[targetState]}.`);
      return;
    }
    if (!leagueId) {
      setError("Seleziona una lega prima di cambiarne lo stato.");
      return;
    }
    const stored = loadStoredSession();
    if (!stored?.accessToken) {
      setError("Sessione non disponibile. Accedi di nuovo.");
      return;
    }
    setWorking(targetState);
    try {
      const updated = await transitionLeagueState(stored.accessToken, leagueId, { targetState });
      onChange(updated);
      setSuccess(`Stato aggiornato: ${STATE_LABELS[updated.state]}.`);
    } catch (caught) {
      setError(getApiErrorMessage(caught, "Impossibile aggiornare lo stato della lega."));
    } finally {
      setWorking(null);
    }
  }

  return (
    <section className="fa-season-panel" data-testid="league-season-panel">
      <h2>Stato e avvio stagione</h2>
      <p>
        Stato corrente: <strong>{STATE_LABELS[lifecycle.state]}</strong>
      </p>

      {lifecycle.blockers.length > 0 ? (
        <div data-testid="league-season-blockers">
          <h3>Prerequisiti mancanti</h3>
          <ul>
            {lifecycle.blockers.map((blocker) => (
              <li key={blocker.code}>{blocker.message}</li>
            ))}
          </ul>
        </div>
      ) : null}

      {error ? (
        <UiStatePanel
          state="error"
          title="Stato non aggiornato"
          message={error}
          testId="league-season-transition-error"
        />
      ) : null}
      {success ? (
        <UiStatePanel
          state="success"
          title="Stato aggiornato"
          message={success}
          testId="league-season-transition-success"
        />
      ) : null}

      {lifecycle.allowedTransitions.length === 0 ? (
        <UiStatePanel
          state="empty"
          title="Nessuna transizione disponibile"
          message="Non ci sono ulteriori azioni disponibili per lo stato corrente."
          testId="league-season-no-transitions"
        />
      ) : (
        <div className="fa-ds-showcase__row">
          {lifecycle.allowedTransitions.map((targetState) => (
            <Button
              key={targetState}
              type="button"
              variant="primary"
              disabled={working !== null}
              onClick={() => void transition(targetState)}
              data-testid={`league-season-transition-${targetState}`}
            >
              {working === targetState ? "Aggiornamento…" : ACTION_LABELS[targetState]}
            </Button>
          ))}
        </div>
      )}
    </section>
  );
}
