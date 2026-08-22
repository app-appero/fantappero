import type { LeagueMember } from "@fantappero/contracts";
import { Button, UiStatePanel } from "@fantappero/ui";
import { useCallback, useEffect, useState } from "react";
import {
  fetchLeagueMembers,
  removeLeagueMember,
  transferLeagueAdmin,
} from "../api/leagues";
import { getApiErrorMessage } from "../auth/AuthContext";
import { loadStoredSession } from "../auth/sessionStorage";

const DEMO_MEMBERS: LeagueMember[] = [
  {
    userId: "demo-admin",
    displayName: "Marco",
    role: "league_admin",
    joinedAt: "2026-08-01T10:00:00Z",
  },
  {
    userId: "demo-member-1",
    displayName: "Giulia",
    role: "member",
    joinedAt: "2026-08-02T10:00:00Z",
  },
  {
    userId: "demo-member-2",
    displayName: "Luca",
    role: "member",
    joinedAt: "2026-08-03T10:00:00Z",
  },
];

type LeagueMembersPanelProps = {
  leagueId: string | null;
  isDemoMode: boolean;
  search: string;
};

export function LeagueMembersPanel({
  leagueId,
  isDemoMode,
  search,
}: LeagueMembersPanelProps) {
  const demoState = new URLSearchParams(search).get("partecipanti");
  const [members, setMembers] = useState<LeagueMember[]>(
    isDemoMode && demoState !== "empty" ? DEMO_MEMBERS : [],
  );
  const [loading, setLoading] = useState(!isDemoMode || demoState === "loading");
  const [error, setError] = useState<string | null>(
    isDemoMode && demoState === "error"
      ? "Impossibile caricare i partecipanti (demo)."
      : null,
  );
  const [success, setSuccess] = useState<string | null>(null);
  const [workingId, setWorkingId] = useState<string | null>(null);

  const loadMembers = useCallback(async () => {
    setSuccess(null);
    if (isDemoMode) {
      setLoading(demoState === "loading");
      setError(
        demoState === "error" ? "Impossibile caricare i partecipanti (demo)." : null,
      );
      setMembers(demoState === "empty" || demoState === "error" ? [] : DEMO_MEMBERS);
      return;
    }
    if (!leagueId) {
      setLoading(false);
      setMembers([]);
      return;
    }
    const session = loadStoredSession();
    if (!session?.accessToken) {
      setLoading(false);
      setError("Sessione non disponibile. Accedi di nuovo.");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      setMembers(await fetchLeagueMembers(session.accessToken, leagueId));
    } catch (loadError) {
      setMembers([]);
      setError(getApiErrorMessage(loadError, "Impossibile caricare i partecipanti."));
    } finally {
      setLoading(false);
    }
  }, [demoState, isDemoMode, leagueId]);

  useEffect(() => {
    void loadMembers();
  }, [loadMembers]);

  async function onTransfer(target: LeagueMember) {
    setError(null);
    setSuccess(null);
    if (isDemoMode) {
      setMembers((current) =>
        current.map((member) => ({
          ...member,
          role: member.userId === target.userId ? "league_admin" : "member",
        })),
      );
      setSuccess(`Ruolo di amministratore trasferito a ${target.displayName}.`);
      return;
    }
    const session = loadStoredSession();
    if (!leagueId || !session?.accessToken) {
      setError("Sessione non disponibile. Accedi di nuovo.");
      return;
    }
    setWorkingId(`transfer-${target.userId}`);
    try {
      const transferred = await transferLeagueAdmin(
        session.accessToken,
        leagueId,
        target.userId,
      );
      setMembers((current) =>
        current.map((member) => ({
          ...member,
          role: member.userId === transferred.userId ? "league_admin" : "member",
        })),
      );
      setSuccess(`Ruolo di amministratore trasferito a ${transferred.displayName}.`);
    } catch (transferError) {
      setError(getApiErrorMessage(transferError, "Impossibile trasferire il ruolo."));
    } finally {
      setWorkingId(null);
    }
  }

  async function onRemove(target: LeagueMember) {
    setError(null);
    setSuccess(null);
    if (isDemoMode) {
      setMembers((current) => current.filter((member) => member.userId !== target.userId));
      setSuccess(`${target.displayName} è stato rimosso dalla lega.`);
      return;
    }
    const session = loadStoredSession();
    if (!leagueId || !session?.accessToken) {
      setError("Sessione non disponibile. Accedi di nuovo.");
      return;
    }
    setWorkingId(`remove-${target.userId}`);
    try {
      const removed = await removeLeagueMember(session.accessToken, leagueId, target.userId);
      setMembers((current) => current.filter((member) => member.userId !== removed.userId));
      setSuccess(`${removed.displayName} è stato rimosso dalla lega.`);
    } catch (removeError) {
      setError(getApiErrorMessage(removeError, "Impossibile rimuovere il partecipante."));
    } finally {
      setWorkingId(null);
    }
  }

  return (
    <section className="fa-members" aria-labelledby="league-members-title">
      <h2 id="league-members-title">Partecipanti iscritti</h2>
      <p>Trasferisci il ruolo admin o rimuovi un partecipante prima dell’avvio.</p>

      {loading ? (
        <UiStatePanel
          state="loading"
          title="Caricamento partecipanti"
          message="Recupero dei membri della lega in corso…"
          testId="league-members-loading"
        />
      ) : null}
      {!loading && error ? (
        <div>
          <UiStatePanel
            state="error"
            title="Partecipanti non disponibili"
            message={error}
            testId="league-members-error"
          />
          <Button type="button" variant="ghost" onClick={() => void loadMembers()}>
            Riprova
          </Button>
        </div>
      ) : null}
      {!loading && !error && members.length === 0 ? (
        <UiStatePanel
          state="empty"
          title="Nessun partecipante"
          message="Non risultano partecipanti iscritti alla lega."
          testId="league-members-empty"
        />
      ) : null}
      {!loading && !error && members.length > 0 ? (
        <ul className="fa-member-list" data-testid="league-members-list">
          {members.map((member) => (
            <li key={member.userId} className="fa-member-list__item">
              <span>
                <strong>{member.displayName}</strong>
                {` · ${member.role === "league_admin" ? "Amministratore" : "Partecipante"}`}
              </span>
              {member.role === "member" ? (
                <span className="fa-ds-showcase__row">
                  <Button
                    type="button"
                    variant="secondary"
                    size="sm"
                    loading={workingId === `transfer-${member.userId}`}
                    disabled={workingId !== null}
                    onClick={() => void onTransfer(member)}
                  >
                    Trasferisci admin
                  </Button>
                  <Button
                    type="button"
                    variant="danger"
                    size="sm"
                    loading={workingId === `remove-${member.userId}`}
                    disabled={workingId !== null}
                    onClick={() => void onRemove(member)}
                  >
                    Rimuovi
                  </Button>
                </span>
              ) : null}
            </li>
          ))}
        </ul>
      ) : null}
      {success ? (
        <UiStatePanel
          state="success"
          title="Partecipanti aggiornati"
          message={success}
          testId="league-members-success"
        />
      ) : null}
    </section>
  );
}
