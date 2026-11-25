import type {
  CalendarRosterTeamIssues,
  CalendarWindow,
  LeagueCalendar,
  LeagueCalendarPlan,
} from "@fantappero/contracts";
import { Badge, Button, Modal, UiStatePanel } from "@fantappero/ui";
import { useCallback, useEffect, useState } from "react";
import { ApiError } from "../api/client";
import {
  calendarRosterIssuesFromError,
  confirmLeagueCalendar,
  ensureFantasyTurns,
  fetchLeagueCalendarAdmin,
  fetchLeagueCalendarRosterCheck,
  generateLeagueCalendar,
} from "../api/leagues";
import { getApiErrorMessage } from "../auth/AuthContext";
import { loadStoredSession } from "../auth/sessionStorage";
import { useNavigate } from "../router/simpleRouter";

const DEMO_CALENDAR: LeagueCalendar = {
  id: "demo-calendar",
  leagueId: "demo-league",
  status: "draft",
  format: "single_round_robin",
  algorithmVersion: "circle_rr_v1",
  participantCount: 4,
  roundCount: 3,
  matchupCount: 6,
  byeCount: 0,
  generatedAt: "2026-08-04T08:00:00.000Z",
  confirmedAt: null,
  summary: { message: "Anteprima calendario: conferma per associarlo alla lega." },
  rounds: [
    {
      roundNumber: 1,
      matchups: [
        {
          slotIndex: 0,
          isBye: false,
          homeUserId: "a",
          homeDisplayName: "Marco",
          awayUserId: "b",
          awayDisplayName: "Giulia",
        },
        {
          slotIndex: 1,
          isBye: false,
          homeUserId: "c",
          homeDisplayName: "Luca",
          awayUserId: "d",
          awayDisplayName: "Sara",
        },
      ],
    },
  ],
};

type Props = {
  leagueId: string | null;
  isDemoMode: boolean;
  search: string;
  /** Notifica il parent (MatchdayPage) per ricaricare il pannello H2H sotto. */
  onCalendarChanged?: () => void;
};

const WINDOW_DATE = new Intl.DateTimeFormat("it-IT", {
  day: "2-digit",
  month: "2-digit",
  year: "numeric",
  // Date delle finestre in ora italiana, non nel fuso del browser.
  timeZone: "Europe/Rome",
});

function windowLabel(window: CalendarWindow): string {
  const start = new Date(window.startAt);
  const end = new Date(window.endAt);
  const kind = window.kind === "weekend" ? "Weekend" : "Infrasettimanale";
  return `${kind} ${WINDOW_DATE.format(start)} – ${WINDOW_DATE.format(end)}`;
}

/** Diagnostica finestre europee: usate, scartate e motivo (EP13-P03). */
export function CalendarWindowsPanel({ plan }: { plan: LeagueCalendarPlan }) {
  return (
    <section aria-labelledby="calendar-windows-title" data-testid="calendar-windows">
      <h3 id="calendar-windows-title">Finestre europee</h3>
      <p data-testid="calendar-windows-summary">{plan.summary}</p>
      <ul>
        <li>
          Cicli completi: <strong>{plan.cycleCount}</strong> da {plan.cycleLength} giornate
        </li>
        <li>
          Finestre eleggibili: <strong>{plan.eligibleWindowCount}</strong> · usate{" "}
          <strong>{plan.windowsUsed.length}</strong>
        </li>
        <li>
          Riposi: <strong>{plan.byeCount}</strong> · algoritmo{" "}
          <code>{plan.algorithmVersion}</code>
        </li>
      </ul>

      {plan.stale ? (
        <Badge variant="warning" data-testid="calendar-windows-stale">
          Anteprima non aggiornata
        </Badge>
      ) : null}

      {plan.windowsDiscarded.length > 0 ? (
        <details data-testid="calendar-windows-discarded">
          <summary>Finestre non utilizzate ({plan.windowsDiscarded.length})</summary>
          <ul>
            {plan.windowsDiscarded.map((window) => (
              <li key={window.startAt}>
                {windowLabel(window)} — {window.fixtureCount}/{window.minRequired} partite.{" "}
                {window.reason ?? "Nessun motivo registrato."}
              </li>
            ))}
          </ul>
        </details>
      ) : null}
    </section>
  );
}

export type CalendarAction = "generate" | "confirm";

/** Stato del modale di «Genera/Conferma calendario»: verifica rose, poi conferma o avviso. */
export type CalendarActionModalState = {
  action: CalendarAction;
  phase: "checking" | "ready";
  teams: CalendarRosterTeamIssues[];
};

const ACTION_COPY: Record<
  CalendarAction,
  { title: string; verb: string; button: string; forceButton: string; working: string; prompt: string }
> = {
  generate: {
    title: "Genera calendario",
    verb: "generare",
    button: "Genera calendario",
    forceButton: "Genera comunque",
    working: "Generazione…",
    prompt:
      "Vuoi generare il calendario? Le giornate seguono i Turni Europei della lega: dopo controlli l'anteprima e la confermi.",
  },
  confirm: {
    title: "Conferma calendario",
    verb: "confermare",
    button: "Conferma calendario",
    forceButton: "Conferma comunque",
    working: "Conferma…",
    prompt: "Vuoi confermare il calendario? Gli scontri diventano visibili a tutti i partecipanti.",
  },
};

function joinTeamNames(names: string[]): string {
  if (names.length <= 1) {
    return names[0] ?? "";
  }
  return `${names.slice(0, -1).join(", ")} e ${names[names.length - 1]}`;
}

/**
 * Modale di «Genera/Conferma calendario» (Rosario 22/11): conferma normale con le rose in
 * regola, altrimenti l'avviso con squadre e problemi e «Genera comunque» / «Conferma comunque».
 *
 * Il testo segue il comportamento reale della formazione (`roster_allows_lineup`,
 * `drop_role_quota_excess_from_tribuna`): chi è in esubero di ruolo resta in rosa ma non si
 * schiera (né titolare né nei primi 10 della panchina), gli altri sì. Una rosa con slot vuoti
 * o meno di 3 campionati (`lineupBlocked`) invece non schiera proprio.
 */
export function CalendarActionModal({
  state,
  working,
  onCancel,
  onProceed,
}: {
  state: CalendarActionModalState | null;
  working: boolean;
  onCancel: () => void;
  onProceed: (force: boolean) => void;
}) {
  const copy = ACTION_COPY[state?.action ?? "generate"];
  const teams = state?.teams ?? [];
  const checking = state?.phase === "checking";
  const hasIssues = !checking && teams.length > 0;
  const blocked = teams.filter((team) => team.lineupBlocked).map((team) => team.teamName);
  return (
    <Modal
      open={state !== null}
      onClose={onCancel}
      title={copy.title}
      className="fa-calendar-action-modal"
      footer={
        <>
          <Button
            type="button"
            variant="ghost"
            onClick={onCancel}
            disabled={working}
            data-testid="league-calendar-modal-cancel"
          >
            Annulla
          </Button>
          <Button
            type="button"
            variant="primary"
            onClick={() => onProceed(hasIssues)}
            disabled={working || checking}
            data-testid="league-calendar-modal-proceed"
          >
            {working ? copy.working : hasIssues ? copy.forceButton : copy.button}
          </Button>
        </>
      }
    >
      {checking ? (
        <p data-testid="league-calendar-modal-checking">Verifica delle rose in corso…</p>
      ) : hasIssues ? (
        <div data-testid="league-calendar-modal-warning">
          <p>
            <strong>Alcune rose non sono in regola:</strong>
          </p>
          <ul className="fa-calendar-action-modal__issues" data-testid="league-calendar-modal-issues">
            {teams.map((team) => (
              <li key={team.teamId ?? team.teamName}>
                <strong>{team.teamName}</strong>: {team.issues.join(", ")}
              </li>
            ))}
          </ul>
          <p>
            Puoi {copy.verb} comunque il calendario: le rose andranno sistemate, meglio prima del
            primo turno. Finché una rosa non torna in regola, i calciatori in esubero restano in
            rosa ma non potranno essere schierati, né titolari né tra i primi 10 della panchina; il
            resto della squadra può schierare la formazione senza di loro.
          </p>
          {blocked.length > 0 ? (
            <p data-testid="league-calendar-modal-blocked">
              {joinTeamNames(blocked)} invece non{" "}
              {blocked.length === 1 ? "potrà" : "potranno"} schierare la formazione finché la rosa
              non sarà completa e con almeno 3 campionati.
            </p>
          ) : null}
        </div>
      ) : (
        <p data-testid="league-calendar-modal-confirm">{copy.prompt}</p>
      )}
    </Modal>
  );
}

function calendarStatusLabel(calendar: LeagueCalendar | null): string {
  if (!calendar) {
    return "Non generato";
  }
  return calendar.status === "confirmed" ? "Confermato" : "Anteprima";
}

function requestedState(search: string): "loading" | "empty" | "error" | "forbidden" | null {
  const value = new URLSearchParams(search).get("calendario");
  return value === "loading" ||
    value === "empty" ||
    value === "error" ||
    value === "forbidden"
    ? value
    : null;
}

export function LeagueCalendarPanel({
  leagueId,
  isDemoMode,
  search,
  onCalendarChanged,
}: Props) {
  const navigate = useNavigate();
  const demoState = isDemoMode ? requestedState(search) : null;
  const [calendar, setCalendar] = useState<LeagueCalendar | null>(() => {
    if (!isDemoMode) {
      return null;
    }
    if (demoState === "empty" || demoState === "error" || demoState === "loading" || demoState === "forbidden") {
      return null;
    }
    return DEMO_CALENDAR;
  });
  const [loading, setLoading] = useState(() => {
    if (isDemoMode) {
      return demoState === "loading";
    }
    return true;
  });
  const [working, setWorking] = useState<CalendarAction | null>(null);
  const [modal, setModal] = useState<CalendarActionModalState | null>(null);
  const [loadError, setLoadError] = useState<string | null>(() =>
    isDemoMode && demoState === "error" ? "Impossibile caricare il calendario (demo)." : null,
  );
  const [actionError, setActionError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const loadCalendar = useCallback(async () => {
    setActionError(null);
    setSuccess(null);
    if (isDemoMode) {
      if (demoState === "loading") {
        setLoading(true);
        setCalendar(null);
        setLoadError(null);
        return;
      }
      if (demoState === "error") {
        setLoading(false);
        setCalendar(null);
        setLoadError("Impossibile caricare il calendario (demo).");
        return;
      }
      if (demoState === "empty") {
        setLoading(false);
        setCalendar(null);
        setLoadError(null);
        return;
      }
      if (demoState === "forbidden") {
        setLoading(false);
        setCalendar(null);
        setLoadError(null);
        return;
      }
      setLoading(false);
      setCalendar(DEMO_CALENDAR);
      setLoadError(null);
      return;
    }

    if (!leagueId) {
      setLoading(false);
      setCalendar(null);
      setLoadError(null);
      return;
    }

    const stored = loadStoredSession();
    if (!stored?.accessToken) {
      setLoading(false);
      setCalendar(null);
      setLoadError("Sessione non disponibile. Accedi di nuovo.");
      return;
    }

    setLoading(true);
    setLoadError(null);
    try {
      const current = await fetchLeagueCalendarAdmin(stored.accessToken, leagueId);
      setCalendar(current);
    } catch (error) {
      setLoadError(getApiErrorMessage(error, "Impossibile caricare il calendario."));
      setCalendar(null);
    } finally {
      setLoading(false);
    }
  }, [demoState, isDemoMode, leagueId]);

  useEffect(() => {
    void loadCalendar();
  }, [loadCalendar]);

  /**
   * «Genera/Conferma calendario» apre il modale: prima si verificano le rose, poi si mostra la
   * conferma normale o l'avviso con «Genera comunque» / «Conferma comunque».
   */
  async function openActionModal(action: CalendarAction) {
    setActionError(null);
    setSuccess(null);
    setModal({ action, phase: "checking", teams: [] });
    const stored = loadStoredSession();
    if (isDemoMode || !leagueId || !stored?.accessToken) {
      setModal({ action, phase: "ready", teams: [] });
      return;
    }
    let teams: CalendarRosterTeamIssues[] = [];
    try {
      teams = (await fetchLeagueCalendarRosterCheck(stored.accessToken, leagueId)).teams;
    } catch {
      // Verifica non riuscita: conferma normale; se le rose non sono in regola lo dice
      // l'azione stessa (`league_rosters_invalid`) e il modale passa all'avviso.
    }
    setModal((current) =>
      current && current.action === action ? { action, phase: "ready", teams } : current,
    );
  }

  function closeActionModal() {
    if (working === null) {
      setModal(null);
    }
  }

  async function runAction(action: CalendarAction, force: boolean) {
    if (action === "generate") {
      await onGenerate(force);
    } else {
      await onConfirm(force);
    }
  }

  /** Errore dell'azione: avviso sulle rose nel modale se è quello, altrimenti nel pannello. */
  function onActionError(action: CalendarAction, error: unknown, fallback: string) {
    const teams = calendarRosterIssuesFromError(error);
    if (teams !== null && teams.length > 0) {
      setModal({ action, phase: "ready", teams });
      return;
    }
    setModal(null);
    setActionError(getApiErrorMessage(error, fallback));
  }

  async function onGenerate(force: boolean) {
    setActionError(null);
    setSuccess(null);
    if (isDemoMode) {
      setModal(null);
      setCalendar(DEMO_CALENDAR);
      setSuccess("Calendario generato.");
      onCalendarChanged?.();
      return;
    }
    if (!leagueId) {
      setModal(null);
      setActionError("Seleziona una lega prima di generare il calendario.");
      return;
    }
    const stored = loadStoredSession();
    if (!stored?.accessToken) {
      setModal(null);
      setActionError("Sessione non disponibile. Accedi di nuovo.");
      return;
    }
    setWorking("generate");
    try {
      let next;
      try {
        next = await generateLeagueCalendar(stored.accessToken, leagueId, { force });
      } catch (error) {
        // I Turni Europei di questa lega non esistono ancora (lega nuova, mai
        // entrata nella finestra del cron automatico che copre solo le leghe
        // già attive): li sincronizziamo al volo e riproviamo, così "Genera
        // calendario" resta un solo bottone per l'intera catena.
        if (!(error instanceof ApiError) || error.code !== "european_turns_missing") {
          throw error;
        }
        await ensureFantasyTurns(stored.accessToken, leagueId);
        next = await generateLeagueCalendar(stored.accessToken, leagueId, { force });
      }
      setModal(null);
      setCalendar(next);
      setSuccess(
        `Calendario generato: ${next.matchupCount} incontri su ${next.roundCount} giornate.`,
      );
      onCalendarChanged?.();
    } catch (error) {
      onActionError("generate", error, "Impossibile generare il calendario.");
    } finally {
      setWorking(null);
    }
  }

  async function onConfirm(force: boolean) {
    setActionError(null);
    setSuccess(null);
    if (isDemoMode) {
      setModal(null);
      setCalendar({
        ...DEMO_CALENDAR,
        status: "confirmed",
        confirmedAt: "2026-08-04T09:00:00.000Z",
        summary: { message: "Calendario confermato e consultabile dai partecipanti." },
      });
      setSuccess("Calendario confermato.");
      onCalendarChanged?.();
      return;
    }
    if (!leagueId) {
      setModal(null);
      setActionError("Seleziona una lega prima di confermare il calendario.");
      return;
    }
    const stored = loadStoredSession();
    if (!stored?.accessToken) {
      setModal(null);
      setActionError("Sessione non disponibile. Accedi di nuovo.");
      return;
    }
    setWorking("confirm");
    try {
      const next = await confirmLeagueCalendar(stored.accessToken, leagueId, { force });
      setModal(null);
      setCalendar(next);
      setSuccess("Calendario confermato.");
      onCalendarChanged?.();
    } catch (error) {
      onActionError("confirm", error, "Impossibile confermare il calendario.");
    } finally {
      setWorking(null);
    }
  }

  if (demoState === "forbidden") {
    return (
      <UiStatePanel
        state="forbidden"
        title="Permessi insufficienti"
        message="Solo l'amministratore della lega può generare il calendario."
        testId="league-calendar-forbidden"
      />
    );
  }

  if (loading || demoState === "loading") {
    return (
      <UiStatePanel
        state="loading"
        title="Caricamento calendario"
        message="Recupero degli scontri diretti in corso…"
        testId="league-calendar-loading"
      />
    );
  }

  if (loadError) {
    return (
      <section className="fa-calendar-panel" data-testid="league-calendar-panel">
        <h2>Calendario fantallenatori</h2>
        <UiStatePanel
          state="error"
          title="Calendario non disponibile"
          message={loadError}
          testId="league-calendar-error"
        />
        <Button type="button" variant="ghost" onClick={() => void loadCalendar()}>
          Riprova
        </Button>
      </section>
    );
  }

  // Dopo la conferma restano solo gli scontri nel pannello H2H sotto:
  // niente più bottoni Genera/Conferma né banner di successo.
  if (calendar?.status === "confirmed") {
    return null;
  }

  const rosterLocked =
    Boolean(actionError) && /Completa le rose|Partecipanti/i.test(actionError ?? "");

  return (
    <section className="fa-calendar-panel" data-testid="league-calendar-panel">
      <h2>Calendario fantallenatori</h2>
      <p>
        Stato: <strong data-testid="league-calendar-status">{calendarStatusLabel(calendar)}</strong>
        {calendar
          ? ` · ${calendar.matchupCount} incontri · ${calendar.roundCount} giornate${
              calendar.byeCount > 0 ? ` · ${calendar.byeCount} riposi` : ""
            }`
          : null}
      </p>
      <p>
        Genera e conferma il calendario quando tutte le rose in Partecipanti sono in regola: se
        qualcuna non lo è, prima di procedere ti diciamo quale e cosa manca. Gli scontri
        compaiono sotto, giornata per giornata.
      </p>

      {!calendar ? (
        <UiStatePanel
          state="empty"
          title="Nessun calendario"
          message="Completa le rose di tutti i partecipanti, poi genera il calendario."
          testId="league-calendar-empty"
        />
      ) : null}

      {actionError ? (
        <UiStatePanel
          state="error"
          title="Operazione non completata"
          message={actionError}
          testId="league-calendar-action-error"
        />
      ) : null}
      {rosterLocked ? (
        <Button
          type="button"
          variant="ghost"
          onClick={() => navigate("/lega/amministrazione?setup=invitati")}
          data-testid="league-calendar-goto-participants"
        >
          Vai a Partecipanti
        </Button>
      ) : null}
      {success ? (
        <UiStatePanel
          state="success"
          title="Calendario aggiornato"
          message={success}
          testId="league-calendar-success"
        />
      ) : null}

      <div className="fa-ds-showcase__row">
        <Button
          type="button"
          variant="primary"
          disabled={working !== null || modal !== null}
          onClick={() => void openActionModal("generate")}
          data-testid="league-calendar-generate"
        >
          {working === "generate" ? "Generazione…" : "Genera calendario"}
        </Button>
        <Button
          type="button"
          variant="secondary"
          disabled={working !== null || modal !== null || !calendar}
          onClick={() => void openActionModal("confirm")}
          data-testid="league-calendar-confirm"
        >
          {working === "confirm" ? "Conferma…" : "Conferma calendario"}
        </Button>
      </div>
      <CalendarActionModal
        state={modal}
        working={working !== null}
        onCancel={closeActionModal}
        onProceed={(force) => {
          if (modal) {
            void runAction(modal.action, force);
          }
        }}
      />
    </section>
  );
}
