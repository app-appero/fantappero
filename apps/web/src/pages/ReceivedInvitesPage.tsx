import { Breadcrumb, Button, PageContainer, UiStatePanel } from "@fantappero/ui";
import { useCallback, useEffect, useState } from "react";
import {
  acceptReceivedNamedInvite,
  declineReceivedNamedInvite,
  fetchReceivedNamedInvites,
  type NamedLeagueInvite,
} from "../api/managerInvites";
import { ApiError } from "../api/client";
import { getApiErrorMessage, useAuth } from "../auth/AuthContext";
import { loadStoredSession } from "../auth/sessionStorage";
import { useLocation } from "../router/simpleRouter";

const DEMO_INVITES: NamedLeagueInvite[] = [
  {
    id: "received-demo",
    leagueId: "demo-league-2",
    leagueName: "Amici del Bar",
    recipientUserId: "demo-member",
    recipientDisplayName: "Demo Manager",
    recipientUserType: "human",
    status: "pending",
    createdAt: "2026-08-03T10:00:00Z",
    expiresAt: "2026-08-12T10:00:00Z",
    respondedAt: null,
    autoAccepted: false,
  },
];

function actionError(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 403) return "Non puoi gestire questo invito.";
    if (error.code === "league_capacity_reached") return "La lega ha raggiunto la capienza massima.";
    if (error.code === "invite_not_pending") return "L'invito è già stato gestito o non è più valido.";
  }
  return getApiErrorMessage(error, "Impossibile aggiornare l'invito.");
}

export function ReceivedInvitesPage() {
  const { isDemoMode, registerLeague } = useAuth();
  const { search } = useLocation();
  const demoState = new URLSearchParams(search).get("invitiRicevuti");
  const [invites, setInvites] = useState<NamedLeagueInvite[]>(() =>
    isDemoMode && demoState !== "empty" && demoState !== "error" && demoState !== "forbidden"
      ? DEMO_INVITES
      : [],
  );
  const [loading, setLoading] = useState(!isDemoMode);
  const [error, setError] = useState<string | null>(() => {
    if (!isDemoMode) return null;
    if (demoState === "error") return "Impossibile caricare gli inviti ricevuti (demo).";
    if (demoState === "forbidden") return "Non hai i permessi per visualizzare questi inviti.";
    return null;
  });
  const [success, setSuccess] = useState<string | null>(null);
  const [workingId, setWorkingId] = useState<string | null>(null);

  const load = useCallback(async () => {
    setSuccess(null);
    if (isDemoMode) {
      setLoading(demoState === "loading");
      if (demoState === "error" || demoState === "forbidden") {
        setError(
          demoState === "forbidden"
            ? "Non hai i permessi per visualizzare questi inviti."
            : "Impossibile caricare gli inviti ricevuti (demo).",
        );
        setInvites([]);
        return;
      }
      setError(null);
      setInvites(demoState === "empty" ? [] : DEMO_INVITES);
      return;
    }
    const session = loadStoredSession();
    if (!session?.accessToken) {
      setError("Sessione non disponibile. Accedi di nuovo.");
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      setInvites(await fetchReceivedNamedInvites(session.accessToken));
    } catch (loadError) {
      setError(getApiErrorMessage(loadError, "Impossibile caricare gli inviti ricevuti."));
    } finally {
      setLoading(false);
    }
  }, [demoState, isDemoMode]);

  useEffect(() => {
    void load();
  }, [load]);

  async function act(invite: NamedLeagueInvite, action: "accept" | "decline") {
    setError(null);
    setSuccess(null);
    if (isDemoMode) {
      if (demoState === "capacity" && action === "accept") {
        setError("La lega ha raggiunto la capienza massima.");
        return;
      }
      setInvites((current) => current.filter((row) => row.id !== invite.id));
      setSuccess(action === "accept" ? `Sei entrato in ${invite.leagueName} (demo).` : "Invito rifiutato (demo).");
      return;
    }
    const session = loadStoredSession();
    if (!session?.accessToken) {
      setError("Sessione non disponibile. Accedi di nuovo.");
      return;
    }
    setWorkingId(invite.id);
    try {
      if (action === "accept") {
        await acceptReceivedNamedInvite(session.accessToken, invite.id);
        registerLeague({ id: invite.leagueId, name: invite.leagueName, role: "member" });
        setSuccess(`Sei entrato in ${invite.leagueName}.`);
      } else {
        await declineReceivedNamedInvite(session.accessToken, invite.id);
        setSuccess("Invito rifiutato.");
      }
      setInvites((current) => current.filter((row) => row.id !== invite.id));
    } catch (actionFailure) {
      setError(actionError(actionFailure));
    } finally {
      setWorkingId(null);
    }
  }

  return (
    <PageContainer
      title="Inviti ricevuti"
      header={<Breadcrumb items={[{ label: "Leghe", href: "/leghe" }, { label: "Inviti ricevuti" }]} />}
    >
      {success ? <UiStatePanel state="success" title="Operazione completata" message={success} testId="received-invites-success" /> : null}
      {loading ? <UiStatePanel state="loading" title="Caricamento inviti" message="Recupero degli inviti nominativi in corso…" testId="received-invites-loading" /> : null}
      {!loading && error ? (
        <div>
          <UiStatePanel state="error" title="Inviti non disponibili" message={error} testId="received-invites-error" />
          <Button type="button" variant="ghost" onClick={() => void load()}>Riprova</Button>
        </div>
      ) : null}
      {!loading && !error && invites.length === 0 ? (
        <UiStatePanel state="empty" title="Nessun invito ricevuto" message="Quando qualcuno ti inviterà in una lega, lo vedrai qui." testId="received-invites-empty" />
      ) : null}
      {!loading && !error && invites.length > 0 ? (
        <ul className="fa-received-invites" data-testid="received-invites-list">
          {invites.map((invite) => (
            <li key={invite.id} className="fa-received-invites__item">
              <div>
                <strong>{invite.leagueName}</strong>
                <p>Invito nominativo per {invite.recipientDisplayName}</p>
              </div>
              <div className="fa-ds-showcase__row">
                <Button type="button" size="sm" loading={workingId === invite.id} onClick={() => void act(invite, "accept")}>Accetta</Button>
                <Button type="button" size="sm" variant="danger" disabled={workingId === invite.id} onClick={() => void act(invite, "decline")}>Rifiuta</Button>
              </div>
            </li>
          ))}
        </ul>
      ) : null}
    </PageContainer>
  );
}
