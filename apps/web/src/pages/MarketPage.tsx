import type { FantasyTeam, MarketReleasePreview, MarketReleaseReason } from "@fantappero/contracts";
import {
  Breadcrumb,
  Button,
  PageContainer,
  Select,
  UiStatePanel,
  WireframeSection,
} from "@fantappero/ui";
import { useCallback, useEffect, useMemo, useState } from "react";
import { applyVoluntaryRelease, previewVoluntaryRelease } from "../api/market";
import { fetchMyCredits, fetchMyFantasyTeam } from "../api/leagues";
import { getApiErrorMessage, useAuth } from "../auth/AuthContext";
import { loadStoredSession } from "../auth/sessionStorage";
import { useLocation } from "../router/simpleRouter";
import { parseWireframeStateFromSearch } from "../wireframes/useWireframeState";

const REASON_OPTIONS: Array<{ value: MarketReleaseReason; label: string }> = [
  { value: "voluntary", label: "Svincolo volontario" },
  { value: "league_exit", label: "Uscita dai cinque campionati" },
];

const DEMO_TEAM: FantasyTeam = {
  id: "demo-team",
  leagueId: "demo-league",
  membershipId: "demo-membership",
  userId: "demo-user",
  name: "Squadra Demo",
  rosterSize: 25,
  filledSlots: 1,
  compositionStatus: "incomplete",
  slots: [
    {
      id: "demo-slot-0",
      slotIndex: 0,
      athleteId: "demo-athlete-1",
      athleteName: "P. Fagioli",
      clubName: "Juventus",
      role: "C",
      purchaseCredits: 12,
    },
  ],
};

/** Schermata Mercato: svincolo volontario con recupero crediti (EP08-04 / FR-MKT-02). */
export function MarketPage() {
  const { isDemoMode, activeLeagueId } = useAuth();
  const { search } = useLocation();
  const demoState = isDemoMode ? parseWireframeStateFromSearch(search) : null;

  const [team, setTeam] = useState<FantasyTeam | null>(isDemoMode ? DEMO_TEAM : null);
  const [balance, setBalance] = useState<number | null>(isDemoMode ? 200 : null);
  const [loading, setLoading] = useState(() => (isDemoMode ? demoState === "loading" : true));
  const [loadError, setLoadError] = useState<string | null>(() =>
    isDemoMode && demoState === "error" ? "Impossibile caricare la rosa (demo)." : null,
  );

  const loadTeam = useCallback(async () => {
    if (isDemoMode) {
      setTeam(
        demoState === "empty" || demoState === "error" || demoState === "forbidden"
          ? { ...DEMO_TEAM, slots: [] }
          : DEMO_TEAM,
      );
      setLoading(demoState === "loading");
      setLoadError(demoState === "error" ? "Impossibile caricare la rosa (demo)." : null);
      return;
    }
    if (!activeLeagueId) {
      setLoading(false);
      setTeam(null);
      setLoadError(null);
      return;
    }
    const stored = loadStoredSession();
    if (!stored?.accessToken) {
      setLoading(false);
      setLoadError("Sessione non disponibile. Accedi di nuovo.");
      return;
    }
    setLoading(true);
    setLoadError(null);
    try {
      const [myTeam, credits] = await Promise.all([
        fetchMyFantasyTeam(stored.accessToken, activeLeagueId),
        fetchMyCredits(stored.accessToken, activeLeagueId).catch(() => null),
      ]);
      setTeam(myTeam);
      if (credits) {
        setBalance(credits.balance);
      }
    } catch (error) {
      setTeam(null);
      setLoadError(getApiErrorMessage(error, "Impossibile caricare la rosa."));
    } finally {
      setLoading(false);
    }
  }, [activeLeagueId, demoState, isDemoMode]);

  useEffect(() => {
    void loadTeam();
  }, [loadTeam]);

  const ownedSlots = useMemo(
    () => (team?.slots ?? []).filter((slot) => slot.athleteId !== null),
    [team],
  );

  const slotOptions = useMemo(
    () =>
      ownedSlots.map((slot) => ({
        value: String(slot.slotIndex),
        label: `${slot.athleteName} (${slot.purchaseCredits ?? 0} crediti)`,
      })),
    [ownedSlots],
  );

  const [selectedSlotIndex, setSelectedSlotIndex] = useState("");
  const [reason, setReason] = useState<MarketReleaseReason>("voluntary");
  const [preview, setPreview] = useState<MarketReleasePreview | null>(null);
  const [previewError, setPreviewError] = useState<string | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [applyError, setApplyError] = useState<string | null>(null);
  const [applySuccess, setApplySuccess] = useState<string | null>(null);
  const [applying, setApplying] = useState(false);

  async function handlePreview() {
    if (isDemoMode || !activeLeagueId || selectedSlotIndex === "") {
      return;
    }
    const stored = loadStoredSession();
    if (!stored?.accessToken) {
      setPreviewError("Sessione non disponibile. Accedi di nuovo.");
      return;
    }
    setPreviewLoading(true);
    setPreviewError(null);
    setPreview(null);
    setApplySuccess(null);
    try {
      const result = await previewVoluntaryRelease(
        stored.accessToken,
        activeLeagueId,
        Number(selectedSlotIndex),
        reason,
      );
      setPreview(result);
    } catch (error) {
      setPreviewError(getApiErrorMessage(error, "Impossibile calcolare il rimborso."));
    } finally {
      setPreviewLoading(false);
    }
  }

  async function handleApply() {
    if (isDemoMode || !activeLeagueId || selectedSlotIndex === "") {
      return;
    }
    const stored = loadStoredSession();
    if (!stored?.accessToken) {
      setApplyError("Sessione non disponibile. Accedi di nuovo.");
      return;
    }
    setApplying(true);
    setApplyError(null);
    try {
      const result = await applyVoluntaryRelease(
        stored.accessToken,
        activeLeagueId,
        Number(selectedSlotIndex),
        reason,
      );
      setBalance(result.balance);
      setApplySuccess(
        `${result.athleteName} svincolato: rimborsati ${result.refundCredits} crediti.`,
      );
      setPreview(null);
      setSelectedSlotIndex("");
      await loadTeam();
    } catch (error) {
      setApplyError(getApiErrorMessage(error, "Impossibile completare lo svincolo."));
    } finally {
      setApplying(false);
    }
  }

  if (isDemoMode && demoState === "forbidden") {
    return (
      <PageContainer
        title="Mercato"
        header={<Breadcrumb items={[{ label: "Leghe", href: "/leghe" }, { label: "Mercato" }]} />}
      >
        <UiStatePanel
          state="forbidden"
          title="Permessi insufficienti"
          message="Non hai accesso al mercato di questa lega."
          testId="wireframe-market-forbidden"
        />
      </PageContainer>
    );
  }

  return (
    <PageContainer
      title="Mercato"
      header={<Breadcrumb items={[{ label: "Leghe", href: "/leghe" }, { label: "Mercato" }]} />}
    >
      <div className="fa-market-page">
        {loading ? (
          <UiStatePanel
            state="loading"
            title="Caricamento"
            message="Recupero la tua rosa…"
            testId="wireframe-market-loading"
          />
        ) : null}

        {!loading && loadError ? (
          <>
            <UiStatePanel
              state="error"
              title="Rosa non disponibile"
              message={loadError}
              testId="wireframe-market-error"
            />
            <Button variant="secondary" onClick={() => void loadTeam()}>
              Ricarica
            </Button>
          </>
        ) : null}

        {!loading && !loadError && !isDemoMode && !activeLeagueId ? (
          <UiStatePanel
            state="empty"
            title="Nessuna lega selezionata"
            message="Scegli una lega per accedere al mercato."
            testId="wireframe-market-no-league"
          />
        ) : null}

        {!loading && !loadError && (isDemoMode || activeLeagueId) ? (
          <WireframeSection label="Svincolo volontario" testId="market-release-section">
            {ownedSlots.length === 0 ? (
              <UiStatePanel
                state="empty"
                title="Nessun giocatore da svincolare"
                message="La tua rosa non ha ancora giocatori assegnati."
                testId="wireframe-market-success"
              />
            ) : (
              <div data-testid="wireframe-market-success">
                <p>Budget residuo: {balance !== null ? `${balance} crediti` : "—"}</p>
                <Select
                  label="Giocatore da svincolare"
                  name="release-slot"
                  options={slotOptions}
                  placeholder="Scegli un giocatore…"
                  value={isDemoMode ? undefined : selectedSlotIndex}
                  onChange={
                    isDemoMode
                      ? undefined
                      : (event) => {
                          setSelectedSlotIndex(event.target.value);
                          setPreview(null);
                          setApplySuccess(null);
                        }
                  }
                  disabled={isDemoMode}
                />
                <Select
                  label="Motivo"
                  name="release-reason"
                  options={REASON_OPTIONS}
                  value={isDemoMode ? undefined : reason}
                  onChange={
                    isDemoMode
                      ? undefined
                      : (event) => {
                          setReason(event.target.value as MarketReleaseReason);
                          setPreview(null);
                        }
                  }
                  disabled={isDemoMode}
                />

                <div className="fa-ds-showcase__row">
                  <Button
                    variant="secondary"
                    disabled={isDemoMode || selectedSlotIndex === "" || previewLoading}
                    onClick={() => void handlePreview()}
                  >
                    {previewLoading ? "Calcolo…" : "Calcola rimborso"}
                  </Button>
                  <Button
                    variant="primary"
                    disabled={isDemoMode || !preview || applying}
                    onClick={() => void handleApply()}
                  >
                    {applying ? "Conferma…" : "Conferma svincolo"}
                  </Button>
                </div>

                {previewError ? (
                  <UiStatePanel
                    state="error"
                    title="Anteprima non disponibile"
                    message={previewError}
                    testId="market-release-preview-error"
                  />
                ) : null}

                {preview ? (
                  <p data-testid="market-release-preview">
                    Rimborso stimato: {preview.refundCredits} crediti ({preview.refundPercent}% di{" "}
                    {preview.purchaseCredits})
                  </p>
                ) : null}

                {applyError ? (
                  <UiStatePanel
                    state="error"
                    title="Svincolo non riuscito"
                    message={applyError}
                    testId="market-release-apply-error"
                  />
                ) : null}

                {applySuccess ? (
                  <UiStatePanel
                    state="success"
                    title="Fatto"
                    message={applySuccess}
                    testId="market-release-apply-success"
                  />
                ) : null}
              </div>
            )}
          </WireframeSection>
        ) : null}
      </div>
    </PageContainer>
  );
}
