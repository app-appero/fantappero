import type {
  FantasyTurnDetail,
  FantasyTurnKind,
  FantasyTurnPreview,
  FantasyTurnSummary,
  H2HCalendar,
} from "@fantappero/contracts";
import { mapFixtureMatchStatus } from "@fantappero/contracts";
import { theme } from "@fantappero/ui/theme";
import { useNavigation, type NavigationProp } from "@react-navigation/core";
import { useCallback, useEffect, useState } from "react";
import {
  Pressable,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import {
  ensureFantasyTurns,
  excludeFantasyTurnFixture,
  fetchFantasyTurn,
  fetchFantasyTurns,
  fetchH2HCalendar,
  generateFantasyTurn,
  openFantasyTurn,
  previewFantasyTurn,
  recalculateFantasyTurnCutoff,
} from "../api/leagues";
import { UiStatePanel } from "../components/UiStatePanel";
import { PageContainer } from "../layout/PageContainer";
import { useLiveH2HPolling } from "../matchday/useLiveH2HPolling";
import type { RootStackParamList } from "../navigation/types";
import { MatchdayH2HPanel } from "./matchday/MatchdayH2HPanel";
import { getApiErrorMessage, useAuthSession } from "../session/DemoSessionContext";

const { colors, spacing, typography, radius } = theme;

const STATUS_LABEL: Record<string, string> = {
  scheduled: "Programmato",
  open: "Aperto",
  locked: "Chiuso",
  skipped: "Non disputato",
};

const MATCH_STATUS_LABEL: Record<string, string> = {
  scheduled: "In programma",
  live: "In corso",
  finished: "Terminata",
  postponed: "Rinviata",
};

function formatDateTime(value: string | null): string {
  if (!value) {
    return "—";
  }
  try {
    return new Intl.DateTimeFormat("it-IT", {
      dateStyle: "medium",
      timeStyle: "short",
      timeZone: "Europe/Rome",
    }).format(new Date(value));
  } catch {
    return value;
  }
}

/** Turni — calendario H2H fantallenatori (con dettaglio scontro) + turni europei. */
export function MatchdayScreen() {
  const { accessToken, activeLeagueId, can } = useAuthSession();
  const navigation = useNavigation<NavigationProp<RootStackParamList>>();
  const isAdmin = can(["league:admin"]);
  const canView = can(["matchday:view"]);

  const [tab, setTab] = useState<"calendario" | "europei">("calendario");
  const [h2h, setH2h] = useState<H2HCalendar | null>(null);
  const [h2hLoading, setH2hLoading] = useState(true);
  const [h2hError, setH2hError] = useState<string | null>(null);
  const [turns, setTurns] = useState<FantasyTurnSummary[]>([]);
  const [selected, setSelected] = useState<FantasyTurnDetail | null>(null);
  const [preview, setPreview] = useState<FantasyTurnPreview | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [actionMessage, setActionMessage] = useState<string | null>(null);
  const [anchorDate, setAnchorDate] = useState("2026-08-15");
  const [kind, setKind] = useState<FantasyTurnKind>("weekend");

  const loadH2H = useCallback(async () => {
    if (!canView || !accessToken || !activeLeagueId) {
      setH2hLoading(false);
      setH2h(null);
      setH2hError(null);
      return;
    }
    setH2hLoading(true);
    try {
      setH2h(await fetchH2HCalendar(accessToken, activeLeagueId));
      setH2hError(null);
    } catch (error) {
      setH2h(null);
      setH2hError(getApiErrorMessage(error, "Calendario H2H non disponibile."));
    } finally {
      setH2hLoading(false);
    }
  }, [accessToken, activeLeagueId, canView]);

  const { degraded: h2hLiveDegraded } = useLiveH2HPolling(
    accessToken,
    activeLeagueId,
    h2h,
    setH2h,
    tab === "calendario",
  );

  const loadTurns = useCallback(async () => {
    if (!canView) {
      setLoading(false);
      return;
    }
    if (!activeLeagueId) {
      setLoading(false);
      setTurns([]);
      setSelected(null);
      return;
    }
    if (!accessToken) {
      setLoading(false);
      setLoadError("Sessione non disponibile. Accedi di nuovo.");
      return;
    }
    setLoading(true);
    setLoadError(null);
    try {
      const list = await fetchFantasyTurns(accessToken, activeLeagueId);
      setTurns(list);
      if (list.length === 0) {
        setSelected(null);
      } else {
        const first = list[0];
        if (!first) {
          setSelected(null);
        } else {
          const detail = await fetchFantasyTurn(accessToken, activeLeagueId, first.id);
          setSelected(detail);
        }
      }
    } catch (error) {
      setLoadError(getApiErrorMessage(error, "Impossibile caricare i turni."));
      setTurns([]);
      setSelected(null);
    } finally {
      setLoading(false);
    }
  }, [accessToken, activeLeagueId, canView]);

  useEffect(() => {
    void loadH2H();
    void loadTurns();
  }, [loadH2H, loadTurns]);

  if (!canView) {
    return (
      <PageContainer title="Turni" testID="screen-matchday">
        <UiStatePanel
          state="forbidden"
          title="Permessi insufficienti"
          message="Non hai accesso alla consultazione dei turni."
          testID="matchday-forbidden"
        />
      </PageContainer>
    );
  }

  if (loading) {
    return (
      <PageContainer title="Turni" testID="screen-matchday">
        <UiStatePanel
          state="loading"
          title="Caricamento turni"
          message="Recupero del calendario europeo in corso…"
          testID="matchday-loading"
        />
      </PageContainer>
    );
  }

  if (loadError) {
    return (
      <PageContainer title="Turni" testID="screen-matchday">
        <UiStatePanel
          state="error"
          title="Turni non disponibili"
          message={loadError}
          testID="matchday-error"
        />
        <Pressable style={styles.button} onPress={() => void loadTurns()} testID="matchday-reload">
          <Text style={styles.buttonLabel}>Ricarica</Text>
        </Pressable>
      </PageContainer>
    );
  }

  if (!activeLeagueId) {
    return (
      <PageContainer title="Turni" testID="screen-matchday">
        <UiStatePanel
          state="empty"
          title="Nessuna lega attiva"
          message="Seleziona una lega per consultare i turni europei."
          testID="matchday-no-league"
        />
      </PageContainer>
    );
  }

  return (
    <PageContainer title="Turni" testID="screen-matchday">
      <View style={styles.stack}>
        <View style={styles.chipRow} testID="matchday-tabs">
          <Pressable
            style={[styles.chip, tab === "calendario" ? styles.chipActive : null]}
            onPress={() => setTab("calendario")}
            testID="matchday-tab-calendario"
          >
            <Text style={styles.chipLabel}>Calendario fantallenatori</Text>
          </Pressable>
          <Pressable
            style={[styles.chip, tab === "europei" ? styles.chipActive : null]}
            onPress={() => setTab("europei")}
            testID="matchday-tab-europei"
          >
            <Text style={styles.chipLabel}>Turni europei</Text>
          </Pressable>
        </View>

        {tab === "calendario" ? (
          <View testID="matchday-h2h">
            <MatchdayH2HPanel
              calendar={h2h}
              loading={h2hLoading}
              error={h2hError}
              liveDegraded={h2hLiveDegraded}
              canAdmin={isAdmin}
              onRetry={() => void loadH2H()}
              onOpenAdmin={() =>
                navigation.navigate("LeagueAdmin", { leagueId: activeLeagueId ?? undefined })
              }
              onOpenMatchup={(slotId) => navigation.navigate("MatchupDetail", { slotId })}
            />
          </View>
        ) : null}

        {tab === "europei" ? (
          <>
        {turns.length === 0 ? (
          <UiStatePanel
            state="empty"
            title="Nessun turno ancora"
            message="I turni vengono calcolati automaticamente dal sistema in base ai campionati della lega."
            testID="matchday-empty"
          />
        ) : (
          <View style={styles.section} testID="matchday-turn-list">
            {turns.map((turn) => (
              <Pressable
                key={turn.id}
                style={styles.chip}
                onPress={() => {
                  if (!accessToken) {
                    return;
                  }
                  setBusy(true);
                  void fetchFantasyTurn(accessToken, activeLeagueId, turn.id)
                    .then(setSelected)
                    .catch((error) =>
                      setActionError(getApiErrorMessage(error, "Dettaglio non disponibile.")),
                    )
                    .finally(() => setBusy(false));
                }}
                testID={`matchday-turn-${turn.number}`}
              >
                <Text style={styles.chipLabel}>
                  Turno {turn.number} — {STATUS_LABEL[turn.effectiveStatus] ?? turn.effectiveStatus}
                </Text>
              </Pressable>
            ))}
          </View>
        )}

        {selected ? (
          <View style={styles.section} testID="matchday-turn-detail">
            <Text style={styles.heading}>Turno {selected.number}</Text>
            <Text style={styles.body}>
              Stato: {STATUS_LABEL[selected.effectiveStatus] ?? selected.effectiveStatus}
            </Text>
            <Text style={styles.body}>Cutoff: {formatDateTime(selected.cutoffAt)}</Text>
            {selected.fixtures.some((fixture) => fixture.lockLatchedAt) ? (
              <Text style={styles.body} testID="matchday-cutoff-latch">
                Un rinvio non sblocca le partite il cui kickoff originale è già trascorso. Le mosse
                già usate restano consumate.
              </Text>
            ) : null}
            {selected.fixtures.map((fixture) => (
              <View key={fixture.id} style={styles.fixtureRow}>
                <Text style={styles.body}>
                  {fixture.homeClubName} – {fixture.awayClubName} ({formatDateTime(fixture.kickoffAt)}) —{" "}
                  {MATCH_STATUS_LABEL[mapFixtureMatchStatus(fixture.statusShort)] ?? fixture.statusShort}
                  {fixture.lockLatchedAt ? " — bloccata" : ""}
                </Text>
                {isAdmin && selected.modificationAllowed ? (
                  <Pressable
                    style={styles.ghostButton}
                    disabled={busy}
                    onPress={() => {
                      if (!accessToken) {
                        return;
                      }
                      setBusy(true);
                      setActionError(null);
                      void excludeFantasyTurnFixture(accessToken, activeLeagueId, selected.id, {
                        fixtureId: fixture.fixtureId,
                      })
                        .then(async (detail) => {
                          setSelected(detail);
                          setActionMessage("Partita esclusa dal turno.");
                          await loadTurns();
                        })
                        .catch((error) =>
                          setActionError(getApiErrorMessage(error, "Esclusione non consentita.")),
                        )
                        .finally(() => setBusy(false));
                    }}
                    testID={`matchday-exclude-${fixture.fixtureId}`}
                  >
                    <Text style={styles.ghostLabel}>Escludi</Text>
                  </Pressable>
                ) : null}
              </View>
            ))}
            {isAdmin && selected.status === "scheduled" ? (
              <Pressable
                style={styles.button}
                disabled={busy}
                onPress={() => {
                  if (!accessToken) {
                    return;
                  }
                  setBusy(true);
                  void openFantasyTurn(accessToken, activeLeagueId, selected.id)
                    .then((detail) => {
                      setSelected(detail);
                      setActionMessage(`Turno ${detail.number} aperto.`);
                      return loadTurns();
                    })
                    .catch((error) =>
                      setActionError(getApiErrorMessage(error, "Apertura non riuscita.")),
                    )
                    .finally(() => setBusy(false));
                }}
                testID="matchday-open"
              >
                <Text style={styles.buttonLabel}>Apri turno</Text>
              </Pressable>
            ) : null}
            {isAdmin && selected.status !== "skipped" ? (
              <Pressable
                style={styles.secondaryButton}
                disabled={busy}
                onPress={() => {
                  if (!accessToken) {
                    return;
                  }
                  setBusy(true);
                  void recalculateFantasyTurnCutoff(accessToken, activeLeagueId, selected.id)
                    .then((detail) => {
                      setSelected(detail);
                      setActionMessage("Cutoff aggiornato.");
                    })
                    .catch((error) =>
                      setActionError(getApiErrorMessage(error, "Ricalcolo non riuscito.")),
                    )
                    .finally(() => setBusy(false));
                }}
                testID="matchday-recalc"
              >
                <Text style={styles.secondaryLabel}>Ricalcola cutoff</Text>
              </Pressable>
            ) : null}
          </View>
        ) : null}

        {isAdmin ? (
          <View style={styles.section} testID="matchday-admin">
            <Text style={styles.heading}>Calendario turni</Text>
            <Text style={styles.body}>
              Il sistema calcola i turni dai campionati della lega. Puoi forzare un aggiornamento.
            </Text>
            <Pressable
              style={styles.button}
              disabled={busy}
              onPress={() => {
                if (!accessToken) {
                  return;
                }
                setBusy(true);
                void ensureFantasyTurns(accessToken, activeLeagueId)
                  .then(async (result) => {
                    setActionMessage(
                      `Sync: ${result.created} creati, ${result.opened} aperti, ${result.waiting} in attesa.`,
                    );
                    await loadTurns();
                  })
                  .catch((error) =>
                    setActionError(getApiErrorMessage(error, "Sincronizzazione non riuscita.")),
                  )
                  .finally(() => setBusy(false));
              }}
              testID="matchday-ensure"
            >
              <Text style={styles.buttonLabel}>Aggiorna dal calendario</Text>
            </Pressable>
            <Text style={styles.heading}>Manuale avanzato</Text>
            <TextInput
              value={anchorDate}
              onChangeText={setAnchorDate}
              style={styles.input}
              placeholder="YYYY-MM-DD"
              testID="matchday-anchor"
            />
            <Pressable
              style={styles.chip}
              onPress={() => setKind(kind === "weekend" ? "midweek" : "weekend")}
              testID="matchday-kind"
            >
              <Text style={styles.chipLabel}>
                Tipo: {kind === "weekend" ? "Weekend" : "Infrasettimanale"}
              </Text>
            </Pressable>
            <Pressable
              style={styles.secondaryButton}
              disabled={busy}
              onPress={() => {
                if (!accessToken) {
                  return;
                }
                setBusy(true);
                void previewFantasyTurn(accessToken, activeLeagueId, { kind, anchorDate })
                  .then((result) => {
                    setPreview(result);
                    setActionMessage(
                      result.thresholdOk
                        ? `Anteprima: ${result.eligibleCount} partite.`
                        : (result.skipReason ?? "Soglia non raggiunta."),
                    );
                  })
                  .catch((error) =>
                    setActionError(getApiErrorMessage(error, "Anteprima non disponibile.")),
                  )
                  .finally(() => setBusy(false));
              }}
              testID="matchday-preview"
            >
              <Text style={styles.secondaryLabel}>Anteprima</Text>
            </Pressable>
            <Pressable
              style={styles.secondaryButton}
              disabled={busy}
              onPress={() => {
                if (!accessToken) {
                  return;
                }
                setBusy(true);
                void generateFantasyTurn(accessToken, activeLeagueId, { kind, anchorDate })
                  .then(async (detail) => {
                    setSelected(detail);
                    setActionMessage(
                      detail.status === "skipped"
                        ? (detail.skipReason ?? "Turno non disputato.")
                        : `Turno ${detail.number} generato.`,
                    );
                    await loadTurns();
                    setSelected(detail);
                  })
                  .catch((error) =>
                    setActionError(getApiErrorMessage(error, "Generazione non riuscita.")),
                  )
                  .finally(() => setBusy(false));
              }}
              testID="matchday-generate"
            >
              <Text style={styles.secondaryLabel}>Genera turno</Text>
            </Pressable>
            {preview ? (
              <Text style={styles.body} testID="matchday-preview-result">
                {preview.eligibleCount}/{preview.minRequired} — cutoff{" "}
                {formatDateTime(preview.cutoffAt)}
              </Text>
            ) : null}
          </View>
        ) : null}

        {actionMessage ? <Text style={styles.success} testID="matchday-success">{actionMessage}</Text> : null}
        {actionError ? (
          <UiStatePanel
            state="error"
            title="Operazione non riuscita"
            message={actionError}
            testID="matchday-action-error"
          />
        ) : null}
          </>
        ) : null}
      </View>
    </PageContainer>
  );
}

const styles = StyleSheet.create({
  stack: {
    gap: spacing.md,
  },
  section: {
    gap: spacing.sm,
  },
  heading: {
    color: colors.foreground,
    fontSize: typography.fontSize.xl,
    fontWeight: "700",
  },
  body: {
    color: colors.foreground,
    fontSize: typography.fontSize.md,
  },
  chip: {
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.md,
    padding: spacing.sm,
  },
  chipRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacing.sm,
  },
  chipActive: {
    borderColor: colors.accent,
  },
  chipLabel: {
    color: colors.foreground,
  },
  button: {
    backgroundColor: colors.accent,
    borderRadius: radius.md,
    padding: spacing.sm,
    alignItems: "center",
  },
  buttonLabel: {
    color: colors.accentContrast,
    fontWeight: "600",
  },
  secondaryButton: {
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.md,
    padding: spacing.sm,
    alignItems: "center",
  },
  secondaryLabel: {
    color: colors.foreground,
  },
  fixtureRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: spacing.sm,
  },
  ghostButton: {
    borderRadius: radius.md,
    paddingHorizontal: spacing.sm,
    paddingVertical: 4,
  },
  ghostLabel: {
    color: colors.danger,
    fontWeight: "600",
  },
  input: {
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.md,
    padding: spacing.sm,
    color: colors.foreground,
  },
  success: {
    color: colors.foreground,
  },
});
