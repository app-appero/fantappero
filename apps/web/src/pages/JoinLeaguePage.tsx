import type { AcceptedLeagueInvite } from "@fantappero/contracts";
import { Breadcrumb, Button, Input, PageContainer, UiStatePanel } from "@fantappero/ui";
import { type FormEvent, useState } from "react";
import { acceptLeagueInvite } from "../api/leagues";
import { getApiErrorMessage, useAuth } from "../auth/AuthContext";
import { loadStoredSession } from "../auth/sessionStorage";
import { useLocation, useNavigate } from "../router/simpleRouter";

const DEMO_RESULT: AcceptedLeagueInvite = {
  leagueId: "demo-league",
  leagueName: "Lega del Quartiere",
  alreadyMember: false,
};

function goToLeagueHome(
  navigate: ReturnType<typeof useNavigate>,
  registerLeague: ReturnType<typeof useAuth>["registerLeague"],
  result: AcceptedLeagueInvite,
) {
  registerLeague({
    id: result.leagueId,
    name: result.leagueName,
    role: "member",
  });
  navigate(`/lega/home?leagueId=${result.leagueId}`);
}

export function JoinLeaguePage() {
  const { isDemoMode, registerLeague } = useAuth();
  const { search } = useLocation();
  const navigate = useNavigate();
  const params = new URLSearchParams(search);
  const token = params.get("token")?.trim() ?? "";
  const demoState = params.get("stato");
  const [code, setCode] = useState("");
  const [loading, setLoading] = useState(isDemoMode && demoState === "loading");
  const [error, setError] = useState<string | null>(
    isDemoMode && demoState === "error" ? "L'invito non è valido o è scaduto (demo)." : null,
  );
  const [result, setResult] = useState<AcceptedLeagueInvite | null>(
    isDemoMode && demoState === "success" ? DEMO_RESULT : null,
  );

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    if (!token && !code.trim()) {
      setError("Inserisci un codice invito.");
      return;
    }
    if (isDemoMode) {
      setResult(DEMO_RESULT);
      goToLeagueHome(navigate, registerLeague, DEMO_RESULT);
      return;
    }
    const session = loadStoredSession();
    if (!session?.accessToken) {
      setError("Sessione non disponibile. Accedi di nuovo.");
      return;
    }
    setLoading(true);
    try {
      const accepted = await acceptLeagueInvite(
        session.accessToken,
        token ? { token } : { code: code.trim() },
      );
      setResult(accepted);
      goToLeagueHome(navigate, registerLeague, accepted);
    } catch (acceptError) {
      setError(getApiErrorMessage(acceptError, "Impossibile entrare nella lega."));
    } finally {
      setLoading(false);
    }
  }

  return (
    <PageContainer
      title="Entra in una lega"
      header={<Breadcrumb items={[{ label: "Leghe", href: "/leghe" }, { label: "Invito" }]} />}
    >
      {loading ? (
        <UiStatePanel
          state="loading"
          title="Verifica invito"
          message="Controllo validità e capienza della lega…"
          testId="join-league-loading"
        />
      ) : null}
      {!loading && error ? (
        <UiStatePanel
          state="error"
          title="Ingresso non riuscito"
          message={error}
          testId="join-league-error"
        />
      ) : null}
      {!loading && result ? (
        <div>
          <UiStatePanel
            state="success"
            title={result.alreadyMember ? "Sei già nella lega" : "Ingresso completato"}
            message={`Ora fai parte di ${result.leagueName}.`}
            testId="join-league-success"
          />
          <Button
            type="button"
            data-testid="join-league-open-home"
            onClick={() => goToLeagueHome(navigate, registerLeague, result)}
          >
            Apri home lega
          </Button>
        </div>
      ) : null}
      {!loading && !result ? (
        <form onSubmit={(event) => void onSubmit(event)} data-testid="join-league-form">
          <p>
            Ingresso solo su invito: usa il <strong>link</strong> ricevuto oppure inserisci il{" "}
            <strong>codice</strong>. Non esiste una ricerca pubblica delle leghe.
          </p>
          {token ? (
            <p>Il link invito è pronto per essere verificato.</p>
          ) : (
            <Input
              label="Codice invito"
              name="invite-code"
              value={code}
              placeholder="ABCDE-FGHIJ"
              autoComplete="off"
              onChange={(event) => setCode(event.target.value)}
            />
          )}
          <Button type="submit">Entra nella lega</Button>
        </form>
      ) : null}
    </PageContainer>
  );
}
