import type { LeagueLifecycle, LeagueState } from "@fantappero/contracts";
import {
  LEAGUE_LIFECYCLE_ACTION_HINT_LABEL,
  LEAGUE_LIFECYCLE_PHASES,
  describeLeagueLifecycleStep,
  leagueLifecyclePhaseIndex,
} from "@fantappero/contracts";
import { Badge, Button, UiStatePanel } from "@fantappero/ui";
import { useState } from "react";
import { transitionLeagueState } from "../api/leagues";
import { getApiErrorMessage } from "../auth/AuthContext";
import { loadStoredSession } from "../auth/sessionStorage";
import { leagueStateLabel } from "../leagues/leagueLabels";
import { useNavigate } from "../router/simpleRouter";

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

// Selettore della sezione a cui rimandare l'admin per risolvere un blocker
// (EP03-05-UX). "teams" riusa la sezione Partecipanti: è lì che si assegnano
// le rose IA e si verificano i crediti, non esiste (ancora) un pannello dedicato.
// "calendar" non ha un anchor: la generazione/conferma calendario vive in
// Turni ▸ Calendario fantallenatori, quindi richiede una navigazione.
const ACTION_HINT_SELECTOR: Record<"rules" | "members" | "teams", string> = {
  rules: '[data-testid="league-admin-form"]',
  members: '[data-testid="league-members-panel"]',
  teams: '[data-testid="league-members-panel"]',
};

function scrollToActionHint(hint: "rules" | "members" | "teams") {
  document
    .querySelector(ACTION_HINT_SELECTOR[hint])
    ?.scrollIntoView({ behavior: "smooth", block: "start" });
}

export function LeagueSeasonPanel({
  leagueId,
  lifecycle,
  isDemoMode,
  search,
  onChange,
}: Props) {
  const demoState = isDemoMode ? requestedState(search) : null;
  const navigate = useNavigate();
  const [working, setWorking] = useState<LeagueState | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [confirmingRollback, setConfirmingRollback] = useState(false);

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

  const step = describeLeagueLifecycleStep(lifecycle);
  const currentPhaseIndex = leagueLifecyclePhaseIndex(lifecycle.state);

  async function transition(targetState: LeagueState) {
    setError(null);
    setSuccess(null);
    setConfirmingRollback(false);
    if (isDemoMode) {
      onChange({ state: targetState, allowedTransitions: [], blockers: [] });
      setSuccess(`Stato aggiornato: ${leagueStateLabel(targetState)}.`);
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
      setSuccess(`Stato aggiornato: ${leagueStateLabel(updated.state)}.`);
    } catch (caught) {
      setError(getApiErrorMessage(caught, "Impossibile aggiornare lo stato della lega."));
    } finally {
      setWorking(null);
    }
  }

  return (
    <section className="fa-season-panel" data-testid="league-season-panel">
      <h2>Stato e avvio stagione</h2>

      <ol className="fa-lifecycle-stepper" data-testid="league-season-stepper">
        {LEAGUE_LIFECYCLE_PHASES.map((phase, index) => (
          <li
            key={phase.key}
            className={[
              "fa-lifecycle-step",
              index === currentPhaseIndex ? "fa-lifecycle-step--current" : "",
              index < currentPhaseIndex ? "fa-lifecycle-step--done" : "",
            ]
              .filter(Boolean)
              .join(" ")}
            aria-current={index === currentPhaseIndex ? "step" : undefined}
          >
            <span className="fa-lifecycle-step__index">{index + 1}</span>
            <span className="fa-lifecycle-step__label">{phase.label}</span>
          </li>
        ))}
      </ol>

      <p>
        Stato corrente: <strong>{leagueStateLabel(lifecycle.state)}</strong>
      </p>

      {lifecycle.blockers.length > 0 ? (
        <div className="fa-lifecycle-checklist" data-testid="league-season-blockers">
          <h3>Prerequisiti mancanti</h3>
          <ul>
            {lifecycle.blockers.map((blocker) => (
              <li key={blocker.code} className="fa-lifecycle-checklist__item">
                <Badge variant="warning">Da sistemare</Badge>
                <span className="fa-lifecycle-checklist__message">{blocker.message}</span>
                {blocker.actionHint ? (
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    onClick={() => {
                      if (blocker.actionHint === "calendar") {
                        navigate("/turni?tab=calendario");
                        return;
                      }
                      scrollToActionHint(blocker.actionHint!);
                    }}
                  >
                    {LEAGUE_LIFECYCLE_ACTION_HINT_LABEL[blocker.actionHint]} →
                  </Button>
                ) : null}
              </li>
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

      {step.forwardTarget === null ? (
        <UiStatePanel
          state="empty"
          title="Nessuna transizione disponibile"
          message="Non ci sono ulteriori azioni disponibili per lo stato corrente."
          testId="league-season-no-transitions"
        />
      ) : (
        <div className="fa-lifecycle-actions">
          <div className="fa-ds-showcase__row">
            <Button
              type="button"
              variant="primary"
              disabled={!step.forwardEnabled || working !== null}
              onClick={() => void transition(step.forwardTarget!)}
              data-testid="league-season-cta-forward"
            >
              {working === step.forwardTarget ? "Aggiornamento…" : step.forwardLabel}
            </Button>

            {step.rollbackTarget && !confirmingRollback ? (
              <Button
                type="button"
                variant="ghost"
                disabled={working !== null}
                onClick={() => setConfirmingRollback(true)}
                data-testid="league-season-cta-rollback"
              >
                {step.rollbackLabel}
              </Button>
            ) : null}
          </div>

          {step.rollbackTarget && confirmingRollback ? (
            <div className="fa-lifecycle-confirm" data-testid="league-season-rollback-confirm">
              <p>
                Sei sicuro? L&apos;asta in corso verrà interrotta e la lega tornerà in
                configurazione.
              </p>
              <div className="fa-ds-showcase__row">
                <Button
                  type="button"
                  variant="danger"
                  disabled={working !== null}
                  onClick={() => void transition(step.rollbackTarget!)}
                  data-testid="league-season-rollback-confirm-submit"
                >
                  {working === step.rollbackTarget ? "Aggiornamento…" : "Conferma"}
                </Button>
                <Button
                  type="button"
                  variant="ghost"
                  disabled={working !== null}
                  onClick={() => setConfirmingRollback(false)}
                >
                  Annulla
                </Button>
              </div>
            </div>
          ) : null}
        </div>
      )}
    </section>
  );
}


