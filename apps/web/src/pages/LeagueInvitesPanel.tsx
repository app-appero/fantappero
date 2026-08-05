import type { CreatedLeagueInvite, LeagueInvite } from "@fantappero/contracts";
import { Button, Select, UiStatePanel } from "@fantappero/ui";
import { useCallback, useEffect, useState } from "react";
import {
  createLeagueInvite,
  fetchLeagueInvites,
  revokeLeagueInvite,
} from "../api/leagues";
import { getApiErrorMessage } from "../auth/AuthContext";
import { loadStoredSession } from "../auth/sessionStorage";

const DEMO_INVITE: CreatedLeagueInvite = {
  id: "demo-invite",
  leagueId: "demo-league",
  status: "active",
  expiresAt: "2026-08-10T10:00:00Z",
  revokedAt: null,
  createdAt: "2026-08-03T10:00:00Z",
  token: "demo-token",
  code: "FANTA-2026X",
  inviteUrl: "http://localhost:5173/leghe/invito?token=demo-token",
};

type LeagueInvitesPanelProps = {
  leagueId: string | null;
  isDemoMode: boolean;
  search: string;
};

function formatDate(value: string): string {
  return new Intl.DateTimeFormat("it-IT", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

export function LeagueInvitesPanel({
  leagueId,
  isDemoMode,
  search,
}: LeagueInvitesPanelProps) {
  const demoInviteState = new URLSearchParams(search).get("inviti");
  const [invites, setInvites] = useState<LeagueInvite[]>([]);
  const [created, setCreated] = useState<CreatedLeagueInvite | null>(
    isDemoMode && demoInviteState !== "empty" ? DEMO_INVITE : null,
  );
  const [expiresInDays, setExpiresInDays] = useState(7);
  const [loading, setLoading] = useState(!isDemoMode);
  const [error, setError] = useState<string | null>(
    isDemoMode && demoInviteState === "error" ? "Impossibile caricare gli inviti (demo)." : null,
  );
  const [workingId, setWorkingId] = useState<string | null>(null);

  const loadInvites = useCallback(async () => {
    if (isDemoMode) {
      setLoading(demoInviteState === "loading");
      setError(
        demoInviteState === "error" ? "Impossibile caricare gli inviti (demo)." : null,
      );
      setInvites(
        demoInviteState === "empty" || demoInviteState === "error" ? [] : [DEMO_INVITE],
      );
      return;
    }
    if (!leagueId) {
      setLoading(false);
      setInvites([]);
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
      setInvites(await fetchLeagueInvites(session.accessToken, leagueId));
    } catch (loadError) {
      setError(getApiErrorMessage(loadError, "Impossibile caricare gli inviti."));
    } finally {
      setLoading(false);
    }
  }, [demoInviteState, isDemoMode, leagueId]);

  useEffect(() => {
    void loadInvites();
  }, [loadInvites]);

  async function onCreate() {
    setError(null);
    if (isDemoMode) {
      setCreated(DEMO_INVITE);
      setInvites([DEMO_INVITE, ...invites.filter((invite) => invite.id !== DEMO_INVITE.id)]);
      return;
    }
    const session = loadStoredSession();
    if (!leagueId || !session?.accessToken) {
      setError("Seleziona una lega e accedi di nuovo.");
      return;
    }
    setWorkingId("create");
    try {
      const result = await createLeagueInvite(session.accessToken, leagueId, { expiresInDays });
      setCreated(result);
      setInvites((current) => [result, ...current]);
    } catch (createError) {
      setError(getApiErrorMessage(createError, "Impossibile generare l'invito."));
    } finally {
      setWorkingId(null);
    }
  }

  async function onRevoke(inviteId: string) {
    setError(null);
    if (isDemoMode) {
      setInvites((current) =>
        current.map((invite) =>
          invite.id === inviteId
            ? { ...invite, status: "revoked", revokedAt: new Date().toISOString() }
            : invite,
        ),
      );
      return;
    }
    const session = loadStoredSession();
    if (!leagueId || !session?.accessToken) {
      setError("Sessione non disponibile. Accedi di nuovo.");
      return;
    }
    setWorkingId(inviteId);
    try {
      const revoked = await revokeLeagueInvite(session.accessToken, leagueId, inviteId);
      setInvites((current) =>
        current.map((invite) => (invite.id === revoked.id ? revoked : invite)),
      );
    } catch (revokeError) {
      setError(getApiErrorMessage(revokeError, "Impossibile revocare l'invito."));
    } finally {
      setWorkingId(null);
    }
  }

  async function copy(value: string) {
    await navigator.clipboard?.writeText(value);
  }

  return (
    <section className="fa-invites" aria-labelledby="league-invites-title">
      <h2 id="league-invites-title">Inviti</h2>
      <p>Genera un link e un codice validi fino alla scadenza o alla revoca.</p>
      <div className="fa-ds-showcase__row">
        <Select
          label="Durata invito"
          name="invite-expiry"
          value={String(expiresInDays)}
          onChange={(event) => setExpiresInDays(Number(event.target.value))}
          options={[
            { value: "1", label: "1 giorno" },
            { value: "7", label: "7 giorni" },
            { value: "14", label: "14 giorni" },
            { value: "30", label: "30 giorni" },
          ]}
        />
        <Button
          type="button"
          onClick={() => void onCreate()}
          loading={workingId === "create"}
          data-testid="league-invite-create"
        >
          Genera invito
        </Button>
      </div>

      {created ? (
        <div>
          <UiStatePanel
            state="success"
            title="Invito generato"
            message={`Codice ${created.code}. Copia ora link o codice: per sicurezza non saranno mostrati di nuovo.`}
            testId="league-invite-created"
          />
          <div className="fa-ds-showcase__row">
            <Button type="button" variant="secondary" onClick={() => void copy(created.inviteUrl)}>
              Copia link
            </Button>
            <Button type="button" variant="ghost" onClick={() => void copy(created.code)}>
              Copia codice
            </Button>
          </div>
        </div>
      ) : null}

      {loading ? (
        <UiStatePanel
          state="loading"
          title="Caricamento inviti"
          message="Recupero degli inviti in corso…"
          testId="league-invites-loading"
        />
      ) : null}
      {!loading && error ? (
        <div>
          <UiStatePanel
            state="error"
            title="Inviti non disponibili"
            message={error}
            testId="league-invites-error"
          />
          <Button type="button" variant="ghost" onClick={() => void loadInvites()}>
            Riprova
          </Button>
        </div>
      ) : null}
      {!loading && !error && invites.length === 0 ? (
        <UiStatePanel
          state="empty"
          title="Nessun invito"
          message="Genera il primo invito per aggiungere partecipanti."
          testId="league-invites-empty"
        />
      ) : null}
      {!loading && !error && invites.length > 0 ? (
        <ul className="fa-invite-list" data-testid="league-invites-list">
          {invites.map((invite) => (
            <li key={invite.id} className="fa-invite-list__item">
              <span>
                <strong>{invite.status === "active" ? "Attivo" : invite.status === "revoked" ? "Revocato" : "Scaduto"}</strong>
                {` · scade ${formatDate(invite.expiresAt)}`}
              </span>
              {invite.status === "active" ? (
                <Button
                  type="button"
                  variant="danger"
                  size="sm"
                  loading={workingId === invite.id}
                  onClick={() => void onRevoke(invite.id)}
                >
                  Revoca
                </Button>
              ) : null}
            </li>
          ))}
        </ul>
      ) : null}
    </section>
  );
}
