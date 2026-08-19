import type { LeagueCalendar } from "@fantappero/contracts";
import { Button, UiStatePanel } from "@fantappero/ui";
import { useCallback, useEffect, useState } from "react";
import {
  confirmLeagueCalendar,
  fetchLeagueCalendarAdmin,
  generateLeagueCalendar,
} from "../api/leagues";
import { getApiErrorMessage } from "../auth/AuthContext";
import { loadStoredSession } from "../auth/sessionStorage";

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
};

function requestedState(search: string): "loading" | "empty" | "error" | "forbidden" | null {
  const value = new URLSearchParams(search).get("calendario");
  return value === "loading" ||
    value === "empty" ||
    value === "error" ||
    value === "forbidden"
    ? value
    : null;
}

export function LeagueCalendarPanel({ leagueId, isDemoMode, search }: Props) {
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
  const [working, setWorking] = useState<"generate" | "confirm" | null>(null);
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

  async function onGenerate() {
    setActionError(null);
    setSuccess(null);
    if (isDemoMode) {
      setCalendar(DEMO_CALENDAR);
      setSuccess("Anteprima calendario generata.");
      return;
    }
    if (!leagueId) {
      setActionError("Seleziona una lega prima di generare il calendario.");
      return;
    }
    const stored = loadStoredSession();
    if (!stored?.accessToken) {
      setActionError("Sessione non disponibile. Accedi di nuovo.");
      return;
    }
    setWorking("generate");
    try {
      const next = await generateLeagueCalendar(stored.accessToken, leagueId);
      setCalendar(next);
      setSuccess(
        `Anteprima generata: ${next.matchupCount} incontri su ${next.roundCount} turni.`,
      );
    } catch (error) {
      setActionError(getApiErrorMessage(error, "Impossibile generare il calendario."));
    } finally {
      setWorking(null);
    }
  }

  async function onConfirm() {
    setActionError(null);
    setSuccess(null);
    if (isDemoMode) {
      setCalendar({
        ...DEMO_CALENDAR,
        status: "confirmed",
        confirmedAt: "2026-08-04T09:00:00.000Z",
        summary: { message: "Calendario confermato e consultabile dai partecipanti." },
      });
      setSuccess("Calendario confermato.");
      return;
    }
    if (!leagueId) {
      setActionError("Seleziona una lega prima di confermare il calendario.");
      return;
    }
    const stored = loadStoredSession();
    if (!stored?.accessToken) {
      setActionError("Sessione non disponibile. Accedi di nuovo.");
      return;
    }
    setWorking("confirm");
    try {
      const next = await confirmLeagueCalendar(stored.accessToken, leagueId);
      setCalendar(next);
      setSuccess("Calendario confermato.");
    } catch (error) {
      setActionError(getApiErrorMessage(error, "Impossibile confermare il calendario."));
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
        <h2>Calendario scontri diretti</h2>
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

  return (
    <section className="fa-calendar-panel" data-testid="league-calendar-panel">
      <h2>Calendario scontri diretti</h2>
      <p>
        Genera un girone di andata bilanciato: ogni partecipante incontra gli altri una volta,
        con riposo esplicito se il numero è dispari.
      </p>

      {!calendar ? (
        <UiStatePanel
          state="empty"
          title="Nessun calendario"
          message="Genera l'anteprima quando i partecipanti iscritti coincidono con il regolamento."
          testId="league-calendar-empty"
        />
      ) : (
        <div data-testid="league-calendar-preview">
          <p>
            Stato: <strong>{calendar.status === "confirmed" ? "Confermato" : "Anteprima"}</strong>
            {" · "}
            {calendar.matchupCount} incontri · {calendar.roundCount} turni
            {calendar.byeCount > 0 ? ` · ${calendar.byeCount} riposi` : ""}
          </p>
          <ul className="fa-calendar-rounds">
            {calendar.rounds.map((round) => (
              <li key={round.roundNumber}>
                <strong>Turno {round.roundNumber}</strong>
                <ul>
                  {round.matchups.map((matchup) => (
                    <li key={`${round.roundNumber}-${matchup.slotIndex}`}>
                      {matchup.isBye
                        ? `${matchup.homeDisplayName} (riposo)`
                        : `${matchup.homeDisplayName} vs ${matchup.awayDisplayName}`}
                    </li>
                  ))}
                </ul>
              </li>
            ))}
          </ul>
        </div>
      )}

      {actionError ? (
        <UiStatePanel
          state="error"
          title="Operazione non completata"
          message={actionError}
          testId="league-calendar-action-error"
        />
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
          disabled={working !== null}
          onClick={() => void onGenerate()}
          data-testid="league-calendar-generate"
        >
          {working === "generate" ? "Generazione…" : "Genera anteprima"}
        </Button>
        <Button
          type="button"
          variant="secondary"
          disabled={working !== null || !calendar || calendar.status === "confirmed"}
          onClick={() => void onConfirm()}
          data-testid="league-calendar-confirm"
        >
          {working === "confirm" ? "Conferma…" : "Conferma calendario"}
        </Button>
      </div>
    </section>
  );
}
