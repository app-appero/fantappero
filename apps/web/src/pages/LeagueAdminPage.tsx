import type {
  LeagueLifecycle,
  LeagueRules,
  UpdateLeagueRulesRequest,
} from "@fantappero/contracts";
import {
  Breadcrumb,
  Button,
  Input,
  PageContainer,
  Select,
  UiStatePanel,
} from "@fantappero/ui";
import { type FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { fetchLeagueAdminPanel, updateLeagueRules } from "../api/leagues";
import { getApiErrorMessage, useAuth } from "../auth/AuthContext";
import { ManagerDirectory } from "../components/ManagerDirectory";
import { loadStoredSession } from "../auth/sessionStorage";
import { useLocation } from "../router/simpleRouter";
import { parseWireframeStateFromSearch } from "../wireframes/useWireframeState";
import { LeagueCalendarPanel } from "./LeagueCalendarPanel";
import { LeagueDeletePanel } from "./LeagueDeletePanel";
import { LeagueInvitesPanel } from "./LeagueInvitesPanel";
import { LeagueMembersPanel } from "./LeagueMembersPanel";
import { LeagueSeasonPanel } from "./LeagueSeasonPanel";

const DEMO_RULES: LeagueRules = {
  presetName: "standard",
  participantCount: 8,
  participantMin: 4,
  participantMax: 10,
  roster: {
    rosterSize: 35,
    goalkeepers: 3,
    defenders: 11,
    midfielders: 11,
    forwards: 10,
  },
  totalCredits: 1000,
  minFixturesPerRound: 25,
  turnCoverageThreshold: 0.75,
  minutesThreshold: 15,
  voluntaryReleaseRefundPercent: 50,
  leagueExitRefundPercent: 100,
  maxActiveTradeProposalsPerTeam: 10,
  options: {
    allowTrades: true,
    allowManualInvites: true,
    requireTradeApproval: false,
  },
};

const DEMO_LIFECYCLE: LeagueLifecycle = {
  state: "draft",
  allowedTransitions: ["configuring"],
  blockers: [],
};

function toParticipantOptions(min: number, max: number): Array<{ value: string; label: string }> {
  const options: Array<{ value: string; label: string }> = [];
  for (let value = min; value <= max; value += 1) {
    options.push({ value: String(value), label: String(value) });
  }
  return options;
}

function buildPayloadFromRules(rules: LeagueRules): UpdateLeagueRulesRequest {
  return {
    presetName: rules.presetName,
    participantCount: rules.participantCount,
    roster: { ...rules.roster },
    totalCredits: rules.totalCredits,
    minFixturesPerRound: rules.minFixturesPerRound,
    turnCoverageThreshold: rules.turnCoverageThreshold,
    minutesThreshold: rules.minutesThreshold,
    voluntaryReleaseRefundPercent: rules.voluntaryReleaseRefundPercent,
    leagueExitRefundPercent: rules.leagueExitRefundPercent,
    maxActiveTradeProposalsPerTeam: rules.maxActiveTradeProposalsPerTeam,
    options: { ...rules.options },
  };
}

/** Configurazione regolamento lega prima dell'avvio stagione (EP03-02). */
export function LeagueAdminPage() {
  const { isDemoMode, activeLeagueId, activeLeague } = useAuth();
  const { search } = useLocation();
  const demoState = isDemoMode ? parseWireframeStateFromSearch(search) : null;

  const [rules, setRules] = useState<LeagueRules | null>(() =>
    isDemoMode && demoState === "success" ? DEMO_RULES : null,
  );
  const [lifecycle, setLifecycle] = useState<LeagueLifecycle | null>(() =>
    isDemoMode && demoState === "success" ? DEMO_LIFECYCLE : null,
  );
  const [loading, setLoading] = useState(() => (isDemoMode ? demoState === "loading" : true));
  const [loadError, setLoadError] = useState<string | null>(() =>
    isDemoMode && demoState === "error" ? "Impossibile caricare il regolamento (demo)." : null,
  );
  const [saveError, setSaveError] = useState<string | null>(null);
  const [saveSuccess, setSaveSuccess] = useState(false);
  const [saving, setSaving] = useState(false);

  const loadPanel = useCallback(async () => {
    setSaveSuccess(false);
    setSaveError(null);
    if (isDemoMode) {
      if (demoState === "loading") {
        setLoading(true);
        setRules(null);
        setLifecycle(null);
        setLoadError(null);
        return;
      }
      if (demoState === "error") {
        setLoading(false);
        setRules(null);
        setLifecycle(null);
        setLoadError("Impossibile caricare il regolamento (demo).");
        return;
      }
      if (demoState === "empty") {
        setLoading(false);
        setRules(null);
        setLifecycle(null);
        setLoadError(null);
        return;
      }
      setLoading(false);
      setRules(DEMO_RULES);
      setLifecycle(DEMO_LIFECYCLE);
      setLoadError(null);
      return;
    }

    if (!activeLeagueId) {
      setLoading(false);
      setRules(null);
      setLifecycle(null);
      setLoadError(null);
      return;
    }

    const stored = loadStoredSession();
    if (!stored?.accessToken) {
      setLoading(false);
      setRules(null);
      setLoadError("Sessione non disponibile. Accedi di nuovo.");
      return;
    }

    setLoading(true);
    setLoadError(null);
    try {
      const panel = await fetchLeagueAdminPanel(stored.accessToken, activeLeagueId);
      setRules(panel.rules);
      setLifecycle(panel.lifecycle);
    } catch (error) {
      setLoadError(getApiErrorMessage(error, "Impossibile caricare il regolamento."));
      setRules(null);
      setLifecycle(null);
    } finally {
      setLoading(false);
    }
  }, [activeLeagueId, demoState, isDemoMode]);

  useEffect(() => {
    void loadPanel();
  }, [loadPanel]);

  const participantOptions = useMemo(
    () =>
      rules
        ? toParticipantOptions(rules.participantMin, rules.participantMax)
        : toParticipantOptions(DEMO_RULES.participantMin, DEMO_RULES.participantMax),
    [rules],
  );
  const canConfigure =
    lifecycle?.state === "draft" || lifecycle?.state === "configuring";

  function updateLocalRules(next: Partial<LeagueRules>) {
    setRules((current: LeagueRules | null) => {
      if (!current) {
        return current;
      }
      return { ...current, ...next };
    });
  }

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!rules) {
      return;
    }
    setSaveError(null);
    setSaveSuccess(false);

    if (isDemoMode) {
      setSaveSuccess(true);
      return;
    }

    if (!activeLeagueId) {
      setSaveError("Seleziona una lega prima di salvare il regolamento.");
      return;
    }

    const stored = loadStoredSession();
    if (!stored?.accessToken) {
      setSaveError("Sessione non disponibile. Accedi di nuovo.");
      return;
    }

    setSaving(true);
    try {
      const saved = await updateLeagueRules(
        stored.accessToken,
        activeLeagueId,
        buildPayloadFromRules(rules),
      );
      setRules(saved);
      setSaveSuccess(true);
    } catch (error) {
      setSaveError(getApiErrorMessage(error, "Impossibile salvare il regolamento."));
    } finally {
      setSaving(false);
    }
  }

  return (
    <PageContainer
      title="Amministrazione lega"
      header={
        <Breadcrumb
          items={[
            { label: "Leghe", href: "/leghe" },
            { label: "Amministrazione" },
          ]}
        />
      }
    >
      {loading ? (
        <UiStatePanel
          state="loading"
          title="Caricamento configurazione"
          message="Recupero regolamento e opzioni in corso…"
          testId="league-admin-loading"
        />
      ) : null}

      {!loading && loadError ? (
        <UiStatePanel
          state="error"
          title="Errore di caricamento"
          message={loadError}
          testId="league-admin-error"
        />
      ) : null}

      {!loading && !loadError && !rules ? (
        <UiStatePanel
          state="empty"
          title="Nessuna lega selezionata"
          message="Seleziona una lega e imposta il regolamento prima dell'avvio."
          testId="league-admin-empty"
        />
      ) : null}

      {!loading && !loadError && rules ? (
        <>
        <form data-testid="league-admin-form" onSubmit={(event) => void onSubmit(event)}>
          <Select
            label="Preset regolamento"
            name="preset"
            value={rules.presetName}
            onChange={() => undefined}
            options={[{ value: "standard", label: "Standard" }]}
            disabled
          />

          <Select
            label="Partecipanti"
            name="participants"
            value={String(rules.participantCount)}
            onChange={(event) =>
              updateLocalRules({ participantCount: Number(event.target.value) })
            }
            options={participantOptions}
            disabled={!canConfigure}
          />

          <Input
            label="Crediti iniziali"
            name="credits"
            type="number"
            min={1}
            disabled={!canConfigure}
            value={String(rules.totalCredits)}
            onChange={(event) =>
              updateLocalRules({ totalCredits: Number(event.target.value) || 0 })
            }
          />

          <Input
            label="Soglia minuti per il voto"
            name="minutesThreshold"
            type="number"
            min={1}
            max={30}
            disabled={!canConfigure}
            value={String(rules.minutesThreshold)}
            onChange={(event) =>
              updateLocalRules({ minutesThreshold: Number(event.target.value) || 0 })
            }
          />

          <fieldset data-testid="league-admin-roster" style={{ marginBottom: "1rem" }}>
            <legend>Rosa standard (fissa)</legend>
            <p>{`${rules.roster.rosterSize} giocatori: ${rules.roster.goalkeepers}P-${rules.roster.defenders}D-${rules.roster.midfielders}C-${rules.roster.forwards}A`}</p>
          </fieldset>

          <fieldset data-testid="league-admin-options" style={{ marginBottom: "1rem" }}>
            <legend>Opzioni lega</legend>
            <label>
              <input
                type="checkbox"
                disabled={!canConfigure}
                checked={rules.options.allowTrades}
                onChange={(event) =>
                  updateLocalRules({
                    options: {
                      ...rules.options,
                      allowTrades: event.target.checked,
                    },
                  })
                }
              />{" "}
              Abilita scambi
            </label>
            <label>
              <input
                type="checkbox"
                disabled={!canConfigure}
                checked={rules.options.allowManualInvites}
                onChange={(event) =>
                  updateLocalRules({
                    options: {
                      ...rules.options,
                      allowManualInvites: event.target.checked,
                    },
                  })
                }
              />{" "}
              Abilita inviti manuali
            </label>
            <label>
              <input
                type="checkbox"
                disabled={!canConfigure}
                checked={rules.options.requireTradeApproval}
                onChange={(event) =>
                  updateLocalRules({
                    options: {
                      ...rules.options,
                      requireTradeApproval: event.target.checked,
                    },
                  })
                }
              />{" "}
              Richiedi approvazione amministratore per gli scambi
            </label>
          </fieldset>

          <fieldset data-testid="league-admin-market-rules" style={{ marginBottom: "1rem" }}>
            <legend>Regole mercato</legend>

            <Input
              label="Rimborso svincolo volontario (%)"
              name="voluntaryReleaseRefundPercent"
              type="number"
              min={0}
              max={100}
              disabled={!canConfigure}
              value={String(rules.voluntaryReleaseRefundPercent)}
              onChange={(event) =>
                updateLocalRules({
                  voluntaryReleaseRefundPercent: Number(event.target.value) || 0,
                })
              }
            />

            <Input
              label="Rimborso svincolo per uscita dai cinque campionati (%)"
              name="leagueExitRefundPercent"
              type="number"
              min={0}
              max={100}
              disabled={!canConfigure}
              value={String(rules.leagueExitRefundPercent)}
              onChange={(event) =>
                updateLocalRules({
                  leagueExitRefundPercent: Number(event.target.value) || 0,
                })
              }
            />

            <Input
              label="Proposte di scambio attive per squadra (max)"
              name="maxActiveTradeProposalsPerTeam"
              type="number"
              min={1}
              disabled={!canConfigure}
              value={String(rules.maxActiveTradeProposalsPerTeam)}
              onChange={(event) =>
                updateLocalRules({
                  maxActiveTradeProposalsPerTeam: Number(event.target.value) || 1,
                })
              }
            />
          </fieldset>

          {saveError ? (
            <UiStatePanel
              state="error"
              title="Configurazione non salvata"
              message={saveError}
              testId="league-admin-save-error"
            />
          ) : null}

          {saveSuccess ? (
            <UiStatePanel
              state="success"
              title="Configurazione salvata"
              message="Regolamento aggiornato con preset Standard."
              testId="league-admin-save-success"
            />
          ) : null}

          <div className="fa-ds-showcase__row">
            <Button
              type="submit"
              variant="primary"
              disabled={saving || !canConfigure}
              data-testid="league-admin-submit"
            >
              {saving ? "Salvataggio…" : "Salva configurazione"}
            </Button>
            {loadError ? (
              <Button type="button" variant="ghost" onClick={() => void loadPanel()}>
                Riprova
              </Button>
            ) : null}
          </div>
        </form>
        <LeagueMembersPanel
          leagueId={activeLeagueId}
          isDemoMode={isDemoMode}
          search={search}
        />
        <LeagueInvitesPanel
          leagueId={activeLeagueId}
          isDemoMode={isDemoMode}
          search={search}
        />
        <ManagerDirectory
          leagueId={activeLeagueId}
          isDemoMode={isDemoMode}
          search={search}
          title="Inviti nominativi"
          compact
        />
        <LeagueCalendarPanel
          leagueId={activeLeagueId}
          isDemoMode={isDemoMode}
          search={search}
        />
        {lifecycle ? (
          <LeagueSeasonPanel
            leagueId={activeLeagueId}
            lifecycle={lifecycle}
            isDemoMode={isDemoMode}
            search={search}
            onChange={setLifecycle}
          />
        ) : null}
        {lifecycle ? (
          <LeagueDeletePanel
            leagueId={activeLeagueId}
            state={lifecycle.state}
            leagueName={activeLeague?.name ?? "questa lega"}
            isDemoMode={isDemoMode}
          />
        ) : null}
        </>
      ) : null}
    </PageContainer>
  );
}



