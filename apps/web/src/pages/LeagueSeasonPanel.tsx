import type { LeagueLifecycle, LeagueLifecycleActionHint } from "@fantappero/contracts";
import {
  LEAGUE_LIFECYCLE_ACTION_HINT_LABEL,
  LEAGUE_LIFECYCLE_PHASES,
  leagueLifecyclePhaseIndex,
  orderLeagueSetupBlockers,
} from "@fantappero/contracts";
import { Badge, Button, UiStatePanel } from "@fantappero/ui";
import { leagueStateLabel } from "../leagues/leagueLabels";
import { useNavigate } from "../router/simpleRouter";

type Props = {
  leagueId: string | null;
  lifecycle: LeagueLifecycle;
  isDemoMode: boolean;
  search: string;
  /** Apre la tab Inviti (o Configurazione) e scrolla alla sezione target. */
  onOpenSetupHint?: (hint: Exclude<LeagueLifecycleActionHint, "calendar">) => void;
};

function requestedState(search: string): "loading" | "empty" | "error" | null {
  const value = new URLSearchParams(search).get("stagione");
  return value === "loading" || value === "empty" || value === "error" ? value : null;
}

/** Stato stagione in sola lettura: le transizioni avvengono in automatico. */
export function LeagueSeasonPanel({
  lifecycle,
  isDemoMode,
  search,
  onOpenSetupHint,
}: Props) {
  const demoState = isDemoMode ? requestedState(search) : null;
  const navigate = useNavigate();

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
        title="Nessuna informazione di stagione"
        message="La lega non ha ancora prerequisiti di stagione da mostrare."
        testId="league-season-empty"
      />
    );
  }

  const currentPhaseIndex = leagueLifecyclePhaseIndex(lifecycle.state);
  const orderedBlockers = orderLeagueSetupBlockers(lifecycle.blockers);

  return (
    <section className="fa-season-panel" data-testid="league-season-panel">
      <h2>Stato stagione</h2>

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

      {orderedBlockers.length > 0 ? (
        <div className="fa-lifecycle-checklist" data-testid="league-season-blockers">
          <h3>Prerequisiti mancanti</h3>
          <p className="fa-lifecycle-checklist__hint">
            Completa i passaggi in ordine: partecipanti → rose → calendario. I passaggi successivi
            restano bloccati finché il precedente non è completo; la stagione parte in automatico.
          </p>
          <ul>
            {orderedBlockers.map((blocker) => (
              <li
                key={blocker.code}
                className={[
                  "fa-lifecycle-checklist__item",
                  blocker.actionable ? "" : "fa-lifecycle-checklist__item--locked",
                ]
                  .filter(Boolean)
                  .join(" ")}
                data-testid={
                  blocker.actionable
                    ? `league-season-blocker-${blocker.code}`
                    : `league-season-blocker-locked-${blocker.code}`
                }
              >
                <Badge variant={blocker.actionable ? "warning" : "neutral"}>
                  {blocker.actionable ? "Da sistemare" : "In attesa"}
                </Badge>
                <span className="fa-lifecycle-checklist__message">
                  {blocker.actionable
                    ? blocker.message
                    : `Completa prima il passaggio precedente. (${blocker.message})`}
                </span>
                {blocker.actionHint && blocker.actionable ? (
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    onClick={() => {
                      if (blocker.actionHint === "calendar") {
                        navigate("/turni?tab=calendario");
                        return;
                      }
                      onOpenSetupHint?.(blocker.actionHint);
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

      {lifecycle.state === "active" ? (
        <UiStatePanel
          state="empty"
          title="Stagione in corso"
          message="La lega si concluderà automaticamente quando tutte le giornate saranno omologate."
          testId="league-season-in-progress"
        />
      ) : null}

      {lifecycle.state === "concluded" || lifecycle.state === "archived" ? (
        <UiStatePanel
          state="empty"
          title="Stagione conclusa"
          message="Non ci sono ulteriori azioni di lifecycle disponibili."
          testId="league-season-done"
        />
      ) : null}

      {(lifecycle.state === "draft" ||
        lifecycle.state === "configuring" ||
        lifecycle.state === "auction") &&
      orderedBlockers.length === 0 ? (
        <UiStatePanel
          state="empty"
          title="Prerequisiti soddisfatti"
          message="La stagione parte in automatico non appena i controlli di avvio sono completi."
          testId="league-season-auto-ready"
        />
      ) : null}
    </section>
  );
}
