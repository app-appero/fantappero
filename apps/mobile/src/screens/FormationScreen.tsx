import type {
  AiLineupRun,
  FantasyModule,
  FantasyTurnSummary,
  LineupContext,
  LineupRole,
} from "@fantappero/contracts";
import {
  APPROVED_MODULES,
  MAX_AUTOMATIC_SUBSTITUTIONS,
  MAX_TACTICAL_MOVES,
  evaluateBenchOrderLock,
  evaluateLineup,
  evaluateProgressiveLock,
  evaluateTacticalMove,
  isAthleteKickoffLocked,
  moveBenchToIndex,
  orderedBenchFromRoster,
  preserveLockedStarters,
  slotsFromLineupIds,
  starterTemplate,
} from "@fantappero/contracts";
import { theme } from "@fantappero/ui/theme";
import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react";
import { Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import {
  fetchFantasyTurns,
  fetchMyLineup,
  copyPreviousLineupToDraft,
  runAiLineups,
  saveLineupDraft,
  saveMyLineup,
} from "../api/leagues";
import { UiStatePanel } from "../components/UiStatePanel";
import { PageContainer } from "../layout/PageContainer";
import { getApiErrorMessage, useAuthSession } from "../session/DemoSessionContext";

const { colors, spacing, typography, radius } = theme;

const ROLE_LABEL: Record<LineupRole, string> = {
  P: "P",
  D: "D",
  C: "C",
  A: "A",
};

/** Esito del calcolo automatico per squadra (EP13-P05). */
const AI_OUTCOME_LABEL: Record<string, string> = {
  created: "Creata",
  updated: "Aggiornata",
  preview: "Anteprima",
  skipped_not_ai: "Squadra manuale, ignorata",
  skipped_locked: "Lock progressivo attivo, invariata",
  skipped_manual: "Formazione manuale esistente, non sovrascritta",
  incomplete: "Rosa insufficiente per il modulo",
};

function roleBadgeColors(role: string | null | undefined): { backgroundColor: string; color: string } {
  if (role === "P") {
    return { backgroundColor: colors.success, color: colors.accentContrast };
  }
  if (role === "D") {
    return { backgroundColor: colors.warning, color: colors.background };
  }
  if (role === "C") {
    return { backgroundColor: colors.accent, color: colors.accentContrast };
  }
  if (role === "A") {
    return { backgroundColor: colors.danger, color: colors.accentContrast };
  }
  return { backgroundColor: colors.border, color: colors.foreground };
}

const KICKOFF_LOCK_MESSAGE =
  "Uno o più calciatori non sono più modificabili: la loro partita è già iniziata.";

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

function BenchOrderPicker({
  playerName,
  index,
  length,
  disabled,
  canMoveTo,
  onMove,
  testID,
  children,
}: {
  playerName: string;
  index: number;
  length: number;
  disabled: boolean;
  canMoveTo: (target: number) => boolean;
  onMove: (target: number) => void;
  testID: string;
  children: ReactNode;
}) {
  const [open, setOpen] = useState(false);
  return (
    <View>
      <View style={styles.row}>
        <Pressable
          accessibilityLabel={`Ordine di ingresso di ${playerName}`}
          accessibilityRole="button"
          disabled={disabled}
          onPress={() => setOpen((current) => !current)}
          style={[styles.orderTrigger, disabled ? styles.disabled : null]}
          testID={testID}
        >
          <Text style={styles.chipLabel}>{index + 1}°</Text>
        </Pressable>
        {children}
      </View>
      {open && !disabled ? (
        <View style={styles.orderMenu}>
          {Array.from({ length }, (_, target) => {
            const allowed = canMoveTo(target);
            return (
              <Pressable
                key={target}
                disabled={!allowed}
                style={[
                  styles.chip,
                  target === index ? styles.chipActive : null,
                  !allowed ? styles.disabled : null,
                ]}
                onPress={() => {
                  onMove(target);
                  setOpen(false);
                }}
              >
                <Text style={styles.chipLabel}>{target + 1}°</Text>
              </Pressable>
            );
          })}
        </View>
      ) : null}
    </View>
  );
}

/** Formazione: copia precedente, bozza e tre mosse tattiche (EP06-05 / EP06-06). */
export function FormationScreen() {
  const { accessToken, activeLeagueId, can } = useAuthSession();
  const canView = can(["roster:view"]);
  const canEdit = can(["roster:edit"]);
  const isAdmin = can(["league:admin"]);

  const [turns, setTurns] = useState<FantasyTurnSummary[]>([]);
  const [selectedRoundId, setSelectedRoundId] = useState("");
  const [context, setContext] = useState<LineupContext | null>(null);
  const [moduleCode, setModuleCode] = useState<FantasyModule>("4-3-3");
  const [starterIds, setStarterIds] = useState<string[]>(starterTemplate("4-3-3").map(() => ""));
  const [benchIds, setBenchIds] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [actionMessage, setActionMessage] = useState<string | null>(null);
  const [aiLineupRun, setAiLineupRun] = useState<AiLineupRun | null>(null);
  const [aiLineupBusy, setAiLineupBusy] = useState(false);
  const [aiLineupError, setAiLineupError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!canView) {
      setLoading(false);
      return;
    }
    if (!activeLeagueId) {
      setLoading(false);
      setTurns([]);
      setContext(null);
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
      const preferred =
        list.find((turn) => turn.effectiveStatus === "open") ?? list[0] ?? null;
      if (!preferred) {
        setSelectedRoundId("");
        setContext(null);
        return;
      }
      setSelectedRoundId(preferred.id);
      const detail = await fetchMyLineup(accessToken, activeLeagueId, preferred.id);
      setContext(detail);
      applyEditor(detail);
    } catch (error) {
      setLoadError(getApiErrorMessage(error, "Impossibile caricare la formazione."));
      setTurns([]);
      setContext(null);
    } finally {
      setLoading(false);
    }
  }, [accessToken, activeLeagueId, canView]);

  useEffect(() => {
    void load();
  }, [load]);

  function applyEditor(detail: LineupContext) {
    const draft = detail.draft;
    if (draft) {
      const templateSlots = starterTemplate(draft.module);
      const starters = [...draft.starterAthleteIds];
      while (starters.length < templateSlots.length) {
        starters.push("");
      }
      setModuleCode(draft.module);
      setStarterIds(starters.slice(0, templateSlots.length));
      setBenchIds(draft.benchAthleteIds);
      return;
    }
    if (detail.lineup) {
      setModuleCode(detail.lineup.module);
      setStarterIds(detail.lineup.starters.map((player) => player.athleteId));
      setBenchIds(detail.lineup.bench.map((player) => player.athleteId));
      return;
    }
    setModuleCode("4-3-3");
    setStarterIds(starterTemplate("4-3-3").map(() => ""));
    setBenchIds([]);
  }

  /** Preview o ricalcolo delle formazioni delle sole squadre IA (EP13-P05). */
  async function runAiLineupsAction(dryRun: boolean) {
    setAiLineupError(null);
    if (!accessToken || !activeLeagueId || !selectedRoundId) {
      return;
    }
    setAiLineupBusy(true);
    try {
      const run = await runAiLineups(accessToken, activeLeagueId, selectedRoundId, dryRun);
      setAiLineupRun(run);
    } catch (error) {
      setAiLineupError(
        getApiErrorMessage(
          error,
          dryRun ? "Anteprima non disponibile." : "Rigenerazione non riuscita.",
        ),
      );
    } finally {
      setAiLineupBusy(false);
    }
  }

  const roster = context?.roster ?? [];
  const template = starterTemplate(moduleCode);
  const clock = context?.serverNow ? new Date(context.serverNow) : new Date();
  const playerLocked = (athleteId: string) => {
    const player = roster.find((row) => row.athleteId === athleteId);
    if (!player) {
      return false;
    }
    return player.locked === true || isAthleteKickoffLocked(clock, player.kickoffAt, player.fixtureStatus, player.lockLatched);
  };
  const reservedIds = preserveLockedStarters({
    template,
    currentStarters: [
      ...starterIds,
      ...(context?.lineup?.starters ?? []).map((player) => player.athleteId),
    ],
    roster,
    now: clock,
  });
  const displayStarters = template.map(
    (_, index) => reservedIds[index] || starterIds[index] || "",
  );
  const displayBench = orderedBenchFromRoster(
    roster.map((row) => row.athleteId),
    displayStarters,
    benchIds,
  );
  const lockedAthleteIds = roster.filter((row) => playerLocked(row.athleteId)).map((row) => row.athleteId);
  const previousBenchIds =
    context?.lineup?.bench.map((player) => player.athleteId) ?? displayBench;

  function canMoveBenchTo(fromIndex: number, toIndex: number): boolean {
    if (fromIndex === toIndex) {
      return true;
    }
    const next = moveBenchToIndex(displayBench, fromIndex, toIndex);
    if (next.join("\0") === displayBench.join("\0")) {
      return false;
    }
    return (
      evaluateBenchOrderLock({
        previousBench: previousBenchIds,
        proposedBench: next,
        lockedAthleteIds,
      }).length === 0
    );
  }

  function moveBenchTo(fromIndex: number, toIndex: number) {
    if (fromIndex === toIndex) {
      return;
    }
    const next = moveBenchToIndex(displayBench, fromIndex, toIndex);
    const orderIssues = evaluateBenchOrderLock({
      previousBench: previousBenchIds,
      proposedBench: next,
      lockedAthleteIds,
    });
    if (orderIssues.length > 0) {
      setActionError(orderIssues[0]?.message ?? "Modifica fuori tempo.");
      return;
    }
    setBenchIds(next);
    setActionError(null);
    setActionMessage(null);
  }
  const evaluation = evaluateLineup({
    module: moduleCode,
    starters: displayStarters.filter(Boolean).map((athleteId) => ({
      athleteId,
      role: roster.find((row) => row.athleteId === athleteId)?.role ?? null,
    })),
    bench: displayBench.map((athleteId) => ({
      athleteId,
      role: roster.find((row) => row.athleteId === athleteId)?.role ?? null,
    })),
    rosterAthleteIds: roster.map((row) => row.athleteId),
  });
  const maxMoves = context?.maxTacticalMoves ?? MAX_TACTICAL_MOVES;
  const movesUsed = context?.tacticalMovesUsed ?? 0;
  const tacticalEvaluation = evaluateTacticalMove({
    hasSavedLineup: Boolean(context?.lineup),
    anyAthleteLocked: lockedAthleteIds.length > 0,
    movesUsed,
    proposedModule: moduleCode,
    proposedStarterIds: displayStarters,
    proposedBenchIds: displayBench,
    previousModule: context?.lineup?.module,
    previousStarterIds: context?.lineup?.starters.map((player) => player.athleteId) ?? [],
    previousBenchIds: context?.lineup?.bench.map((player) => player.athleteId) ?? [],
    maximum: maxMoves,
  });
  const movesRemaining = tacticalEvaluation.wouldConsume
    ? tacticalEvaluation.remainingAfter
    : (context?.tacticalMovesRemaining ?? maxMoves - movesUsed);

  const optionsForSlot = useMemo(() => {
    return (index: number, role: LineupRole) => {
      const selected = new Set(displayStarters.filter((id, current) => current !== index && id));
      return roster.filter((row) => {
        if (row.role !== role || selected.has(row.athleteId)) {
          return false;
        }
        return true;
      });
    };
  }, [displayStarters, roster]);

  async function save() {
    setActionError(null);
    setActionMessage(null);
    if (!evaluation.valid) {
      setActionError(evaluation.issues[0]?.message ?? "Formazione non valida.");
      return;
    }
    const previousSlots = slotsFromLineupIds(
      context?.lineup?.starters.map((player) => player.athleteId) ?? [],
      context?.lineup?.bench.map((player) => player.athleteId) ?? [],
    );
    const lockIssues = [
      ...evaluateProgressiveLock({
        previousSlots,
        proposedSlots: slotsFromLineupIds(displayStarters, displayBench),
        lockedAthleteIds,
      }),
      ...evaluateBenchOrderLock({
        previousBench: context?.lineup?.bench.map((player) => player.athleteId) ?? [],
        proposedBench: displayBench,
        lockedAthleteIds,
      }),
    ];
    if (lockIssues.length > 0) {
      setActionError(lockIssues[0]?.message ?? "Modifica fuori tempo.");
      return;
    }
    if (tacticalEvaluation.issues.length > 0) {
      setActionError(tacticalEvaluation.issues[0]?.message ?? "Mosse tattiche esaurite.");
      return;
    }
    if (!accessToken || !activeLeagueId || !selectedRoundId) {
      return;
    }
    setBusy(true);
    try {
      const detail = await saveMyLineup(accessToken, activeLeagueId, selectedRoundId, {
        module: moduleCode,
        starterAthleteIds: displayStarters,
        benchAthleteIds: displayBench,
      });
      setContext(detail);
      applyEditor(detail);
      setActionMessage("Formazione salvata.");
    } catch (error) {
      setActionError(getApiErrorMessage(error, "Salvataggio formazione non riuscito."));
    } finally {
      setBusy(false);
    }
  }

  async function copyFromPrevious() {
    setActionError(null);
    setActionMessage(null);
    if (!accessToken || !activeLeagueId || !selectedRoundId) {
      return;
    }
    setBusy(true);
    try {
      const detail = await copyPreviousLineupToDraft(accessToken, activeLeagueId, selectedRoundId);
      setContext(detail);
      applyEditor(detail);
      setActionMessage(
        detail.copyIssues && detail.copyIssues.length > 0
          ? "Formazione precedente copiata in bozza e rivalidata sulla rosa corrente."
          : "Formazione precedente copiata in bozza.",
      );
    } catch (error) {
      setActionError(getApiErrorMessage(error, "Copia della formazione precedente non riuscita."));
    } finally {
      setBusy(false);
    }
  }

  async function saveDraft() {
    setActionError(null);
    setActionMessage(null);
    const previousSlots = slotsFromLineupIds(
      context?.lineup?.starters.map((player) => player.athleteId) ?? [],
      context?.lineup?.bench.map((player) => player.athleteId) ?? [],
    );
    const lockIssues = [
      ...evaluateProgressiveLock({
        previousSlots,
        proposedSlots: slotsFromLineupIds(displayStarters, displayBench),
        lockedAthleteIds,
      }),
      ...evaluateBenchOrderLock({
        previousBench: context?.lineup?.bench.map((player) => player.athleteId) ?? [],
        proposedBench: displayBench,
        lockedAthleteIds,
      }),
    ];
    if (lockIssues.length > 0) {
      setActionError(lockIssues[0]?.message ?? "Modifica fuori tempo.");
      return;
    }
    const draftEvaluation = evaluateLineup({
      module: moduleCode,
      starters: displayStarters.map((athleteId) => ({
        athleteId,
        role: athleteId ? (roster.find((row) => row.athleteId === athleteId)?.role ?? null) : null,
      })),
      bench: displayBench.map((athleteId) => ({
        athleteId,
        role: roster.find((row) => row.athleteId === athleteId)?.role ?? null,
      })),
      rosterAthleteIds: roster.map((row) => row.athleteId),
      strict: false,
    });
    if (!draftEvaluation.valid) {
      setActionError(draftEvaluation.issues[0]?.message ?? "Bozza non valida.");
      return;
    }
    if (!accessToken || !activeLeagueId || !selectedRoundId) {
      return;
    }
    setBusy(true);
    try {
      const detail = await saveLineupDraft(accessToken, activeLeagueId, selectedRoundId, {
        module: moduleCode,
        starterAthleteIds: displayStarters,
        benchAthleteIds: displayBench,
      });
      setContext(detail);
      applyEditor(detail);
      setActionMessage("Bozza salvata. Conferma la formazione quando è completa.");
    } catch (error) {
      setActionError(getApiErrorMessage(error, "Salvataggio bozza non riuscito."));
    } finally {
      setBusy(false);
    }
  }

  if (!canView) {
    return (
      <PageContainer title="Formazione">
        <UiStatePanel
          state="forbidden"
          title="Permessi insufficienti"
          message="Non puoi modificare la formazione di questa squadra."
          testID="formation-forbidden"
        />
      </PageContainer>
    );
  }

  if (loading) {
    return (
      <PageContainer title="Formazione">
        <UiStatePanel
          state="loading"
          title="Caricamento formazione"
          message="Recupero modulo e slot disponibili…"
          testID="formation-loading"
        />
      </PageContainer>
    );
  }

  if (loadError) {
    return (
      <PageContainer title="Formazione">
        <UiStatePanel
          state="error"
          title="Formazione non salvata"
          message={loadError}
          testID="formation-error"
        />
        <Pressable style={styles.button} onPress={() => void load()} testID="formation-retry">
          <Text style={styles.buttonLabel}>Riprova</Text>
        </Pressable>
      </PageContainer>
    );
  }

  if (!activeLeagueId) {
    return (
      <PageContainer title="Formazione">
        <UiStatePanel
          state="empty"
          title="Nessuna lega attiva"
          message="Seleziona una lega per schierare la formazione."
          testID="formation-no-league"
        />
      </PageContainer>
    );
  }

  if (turns.length === 0 || !context) {
    return (
      <PageContainer title="Formazione">
        <UiStatePanel
          state="empty"
          title="Formazione non impostata"
          message="Nessun turno disponibile. I turni europei si generano dal calendario della lega."
          testID="formation-empty"
        />
      </PageContainer>
    );
  }

  return (
    <PageContainer title="Formazione">
      <ScrollView contentContainerStyle={styles.content}>
        {context.lineup?.systemGeneratedAi ? (
          <Text style={styles.meta} testID="formation-ai-badge">
            Gestita automaticamente — formazione scelta dall'automazione IA
            {context.lineup.aiDecidedAt
              ? ` il ${formatDateTime(context.lineup.aiDecidedAt)}`
              : ""}
            {context.lineup.aiAlgorithmVersion
              ? ` · ${context.lineup.aiAlgorithmVersion}`
              : ""}
            .
          </Text>
        ) : null}
        <Text style={styles.meta} testID="formation-cutoff">
          Turno {context.roundNumber} — cutoff {formatDateTime(context.cutoffAt)}
        </Text>
        <Text style={styles.meta} testID="formation-lock-hint">
          {context.modificationAllowed
            ? "I calciatori la cui partita è già iniziata restano bloccati anche se l'orario viene rinviato; gli altri restano modificabili."
            : "Nessun calciatore è più modificabile."}
        </Text>
        <Text style={styles.meta} testID="formation-moves">
          Mosse tattiche: {movesUsed}/{maxMoves} usate — ne restano {movesRemaining}.
        </Text>
        <Text style={styles.meta} testID="formation-moves-hint">
          {tacticalEvaluation.wouldConsume
            ? "Questo salvataggio consumerà 1 mossa tattica."
            : "Questo salvataggio non consuma mosse."}{" "}
          Le sostituzioni automatiche non consumano mosse.
        </Text>
        {context.previousLineup ? (
          <Text style={styles.meta} testID="formation-previous-hint">
            Formazione precedente: turno {context.previousLineup.roundNumber} (
            {context.previousLineup.module}). La copia viene rivalidata su rosa e disponibilità
            correnti.
          </Text>
        ) : (
          <Text style={styles.meta} testID="formation-previous-empty">
            Nessuna formazione precedente da copiare.
          </Text>
        )}
        {context.draft ? (
          <Text style={styles.meta} testID="formation-draft-hint">
            Bozza salvata
            {context.draft.copySourceRoundNumber
              ? ` (copiata dal turno ${context.draft.copySourceRoundNumber})`
              : ""}
            .
          </Text>
        ) : null}
        {actionError ? (
          <Text style={styles.error} testID="formation-action-error">
            {actionError}
          </Text>
        ) : null}

        {isAdmin ? (
          <View style={styles.aiSection} testID="formation-ai-admin">
            <Text style={styles.label}>Formazioni IA</Text>
            <Text style={styles.body}>
              Genera automaticamente la formazione delle sole squadre controllate da un
              fantallenatore IA per questo turno. Non tocca mai le formazioni schierate a mano
              da un umano.
            </Text>
            <View style={styles.row}>
              <Pressable
                style={[styles.button, styles.buttonSecondary, aiLineupBusy ? styles.disabled : null]}
                disabled={aiLineupBusy}
                onPress={() => void runAiLineupsAction(true)}
                testID="formation-ai-preview"
              >
                <Text style={styles.buttonSecondaryLabel}>Anteprima formazioni IA</Text>
              </Pressable>
              <Pressable
                style={[styles.button, aiLineupBusy ? styles.disabled : null]}
                disabled={aiLineupBusy}
                onPress={() => void runAiLineupsAction(false)}
                testID="formation-ai-regenerate"
              >
                <Text style={styles.buttonLabel}>Rigenera formazioni IA</Text>
              </Pressable>
            </View>
            {aiLineupRun ? (
              <View testID="formation-ai-result">
                <Text style={styles.meta} testID="formation-ai-summary">
                  {aiLineupRun.summary} · {aiLineupRun.algorithmVersion}
                  {aiLineupRun.dryRun ? " (anteprima, non salvata)" : ""}
                </Text>
                {aiLineupRun.teams.map((team) => (
                  <Text
                    key={team.fantasyTeamId}
                    style={styles.body}
                    testID={`formation-ai-team-${team.fantasyTeamId}`}
                  >
                    {team.fantasyTeamName || team.fantasyTeamId} —{" "}
                    {AI_OUTCOME_LABEL[team.outcome] ?? team.outcome}
                    {team.starters > 0 ? ` · ${team.starters} titolari` : ""}
                    {team.usedFallback ? " · fallback locale" : ""}
                    {team.message ? ` · ${team.message}` : ""}
                  </Text>
                ))}
              </View>
            ) : null}
            {aiLineupError ? (
              <Text style={styles.error} testID="formation-ai-error">
                {aiLineupError}
              </Text>
            ) : null}
          </View>
        ) : null}

        <Text style={styles.label}>Modulo</Text>
        <View style={styles.row} testID="formation-module">
          {APPROVED_MODULES.map((code) => (
            <Pressable
              key={code}
              style={[styles.chip, moduleCode === code ? styles.chipActive : null]}
              disabled={!context.modificationAllowed || !canEdit}
              onPress={() => {
                const lockedIds = [
                  ...new Set([
                    ...starterIds.filter((id) => id && playerLocked(id)),
                    ...(context.lineup?.starters ?? [])
                      .map((player) => player.athleteId)
                      .filter((id) => playerLocked(id)),
                  ]),
                ];
                const preserved = preserveLockedStarters({
                  template: starterTemplate(code),
                  currentStarters: [...lockedIds, ...starterIds],
                  roster,
                  now: clock,
                });
                if (lockedIds.some((id) => id && !preserved.includes(id))) {
                  setActionError(KICKOFF_LOCK_MESSAGE);
                  return;
                }
                setModuleCode(code);
                setStarterIds(preserved);
                setBenchIds(
                  orderedBenchFromRoster(
                    roster.map((row) => row.athleteId),
                    preserved,
                    benchIds,
                  ),
                );
                setActionMessage(null);
              }}
            >
              <Text style={styles.chipLabel}>{code}</Text>
            </Pressable>
          ))}
        </View>

        {template.map((role, index) => {
          const currentId = displayStarters[index] ?? "";
          const reservedId = reservedIds[index] ?? "";
          const lockedSlot = Boolean(reservedId) || playerLocked(currentId);
          const roleColors = roleBadgeColors(role);
          return (
            <View key={`${moduleCode}-${index}`} testID={`formation-starter-${index}`}>
              <View style={styles.row}>
                <View style={[styles.roleBadge, roleColors]}>
                  <Text style={[styles.roleBadgeText, { color: roleColors.color }]}>{role}</Text>
                </View>
                <Text style={styles.label}>
                  {ROLE_LABEL[role]} {index + 1}
                  {lockedSlot ? " (bloccato)" : ""}
                </Text>
              </View>
              {lockedSlot ? (
                <Text style={styles.error}>
                  Partita già iniziata: sostituirlo con un altro calciatore viene rifiutato.
                </Text>
              ) : null}
              <View style={styles.row}>
                {optionsForSlot(index, role).map((player) => (
                  <Pressable
                    key={player.athleteId}
                    style={[
                      styles.chip,
                      displayStarters[index] === player.athleteId ? styles.chipActive : null,
                    ]}
                    disabled={!context.modificationAllowed || !canEdit}
                    onPress={() => {
                      if (reservedId && player.athleteId !== reservedId) {
                        setActionError(KICKOFF_LOCK_MESSAGE);
                        setStarterIds((current) => {
                          const next = [...current];
                          next[index] = reservedId;
                          return next;
                        });
                        return;
                      }
                      if (playerLocked(player.athleteId) && player.athleteId !== currentId) {
                        setActionError(KICKOFF_LOCK_MESSAGE);
                        return;
                      }
                      const nextStarters = [...starterIds];
                      nextStarters[index] = player.athleteId;
                      setStarterIds(nextStarters);
                      setBenchIds(
                        orderedBenchFromRoster(
                          roster.map((row) => row.athleteId),
                          nextStarters.map((value, slotIndex) => reservedIds[slotIndex] || value || ""),
                          benchIds,
                        ),
                      );
                      setActionError(null);
                      setActionMessage(null);
                    }}
                  >
                    <Text style={styles.chipLabel}>
                      {player.athleteName}
                      {playerLocked(player.athleteId) ? " (bloccato)" : ""}
                    </Text>
                  </Pressable>
                ))}
              </View>
            </View>
          );
        })}

        <Text style={styles.label}>Panchina</Text>
        <Text style={styles.body} testID="formation-sub-hint">
          Entrano al massimo {context.maxAutomaticSubstitutions ?? MAX_AUTOMATIC_SUBSTITUTIONS}{" "}
          panchinari, nell'ordine di ingresso sotto e solo a parità di ruolo. Dal{" "}
          {(context.maxAutomaticSubstitutions ?? MAX_AUTOMATIC_SUBSTITUTIONS) + 1}° in poi restano
          fuori se i {context.maxAutomaticSubstitutions ?? MAX_AUTOMATIC_SUBSTITUTIONS} cambi sono già
          stati usati.
        </Text>
        {displayBench.length === 0 ? (
          <Text style={styles.body} testID="formation-bench-empty">
            Nessun panchinaro: tutti i calciatori sono titolari.
          </Text>
        ) : (
          <View testID="formation-bench-order">
            {displayBench.map((id, index) => {
              const name = roster.find((row) => row.athleteId === id)?.athleteName ?? id;
              const role = roster.find((row) => row.athleteId === id)?.role ?? "?";
              const roleColors = roleBadgeColors(role);
              const maxSubs = context.maxAutomaticSubstitutions ?? MAX_AUTOMATIC_SUBSTITUTIONS;
              const canEnter = index < maxSubs;
              return (
                <View
                  key={id}
                  style={[styles.benchRow, canEnter ? null : styles.benchOverflow]}
                >
                  <BenchOrderPicker
                    playerName={name}
                    index={index}
                    length={displayBench.length}
                    disabled={!context.modificationAllowed || !canEdit}
                    canMoveTo={(target) => canMoveBenchTo(index, target)}
                    onMove={(target) => moveBenchTo(index, target)}
                    testID={`formation-bench-position-${index}`}
                  >
                    <View style={[styles.roleBadge, roleColors]}>
                      <Text style={[styles.roleBadgeText, { color: roleColors.color }]}>
                        {role}
                      </Text>
                    </View>
                    <Text style={styles.body}>
                      {name}
                      {playerLocked(id) ? " — bloccato" : ""}
                    </Text>
                  </BenchOrderPicker>
                  <Text style={styles.meta}>
                    {canEnter ? "può subentrare" : `oltre i ${maxSubs} cambi`}
                  </Text>
                </View>
              );
            })}
          </View>
        )}

        {evaluation.issues.map((issue) => (
          <Text key={`${issue.code}-${issue.message}`} style={styles.error}>
            {issue.message}
          </Text>
        ))}
        {actionMessage ? (
          <Text style={styles.ok} testID="formation-success">
            {actionMessage}
          </Text>
        ) : null}

        <Pressable
          style={[
            styles.button,
            styles.buttonSecondary,
            busy || !context.modificationAllowed || !canEdit || !context.copyAvailable
              ? styles.disabled
              : null,
          ]}
          disabled={busy || !context.modificationAllowed || !canEdit || !context.copyAvailable}
          onPress={() => void copyFromPrevious()}
          testID="formation-copy"
        >
          <Text style={styles.buttonSecondaryLabel}>Copia formazione precedente</Text>
        </Pressable>
        <Pressable
          style={[
            styles.button,
            styles.buttonSecondary,
            busy || !context.modificationAllowed || !canEdit ? styles.disabled : null,
          ]}
          disabled={busy || !context.modificationAllowed || !canEdit}
          onPress={() => void saveDraft()}
          testID="formation-draft"
        >
          <Text style={styles.buttonSecondaryLabel}>Salva bozza</Text>
        </Pressable>
        <Pressable
          style={[
            styles.button,
            busy ||
            !context.modificationAllowed ||
            !canEdit ||
            tacticalEvaluation.issues.length > 0
              ? styles.disabled
              : null,
          ]}
          disabled={
            busy ||
            !context.modificationAllowed ||
            !canEdit ||
            tacticalEvaluation.issues.length > 0
          }
          onPress={() => void save()}
          testID="formation-save"
        >
          <Text style={styles.buttonLabel}>Salva formazione</Text>
        </Pressable>
      </ScrollView>
    </PageContainer>
  );
}

const styles = StyleSheet.create({
  content: {
    gap: spacing.sm,
    paddingBottom: spacing.xl,
  },
  aiSection: {
    gap: spacing.xs,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.md,
    padding: spacing.sm,
    marginTop: spacing.xs,
  },
  meta: {
    color: colors.foregroundMuted,
    fontSize: typography.fontSize.sm,
  },
  label: {
    color: colors.foreground,
    fontWeight: "600",
    marginTop: spacing.xs,
  },
  body: {
    color: colors.foreground,
    fontSize: typography.fontSize.md,
  },
  row: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacing.xs,
  },
  chip: {
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.md,
    paddingHorizontal: spacing.sm,
    paddingVertical: spacing.xs,
  },
  chipActive: {
    borderColor: colors.accent,
  },
  chipLabel: {
    color: colors.foreground,
    fontSize: typography.fontSize.xs,
  },
  button: {
    backgroundColor: colors.accent,
    borderRadius: radius.md,
    padding: spacing.sm,
    alignItems: "center",
    marginTop: spacing.sm,
  },
  buttonLabel: {
    color: colors.accentContrast,
    fontWeight: "600",
  },
  buttonSecondary: {
    backgroundColor: colors.background,
    borderWidth: 1,
    borderColor: colors.border,
  },
  buttonSecondaryLabel: {
    color: colors.foreground,
    fontWeight: "600",
  },
  disabled: {
    opacity: 0.5,
  },
  error: {
    color: colors.danger,
  },
  ok: {
    color: colors.success,
  },
  benchRow: {
    gap: spacing.xs,
    marginBottom: spacing.sm,
  },
  benchOverflow: {
    opacity: 0.65,
  },
  orderTrigger: {
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.md,
    paddingHorizontal: spacing.sm,
    paddingVertical: spacing.xs,
    minWidth: 44,
    alignItems: "center",
  },
  orderMenu: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacing.xs,
    marginTop: spacing.xs,
  },
  roleBadge: {
    minWidth: 28,
    height: 28,
    borderRadius: radius.sm,
    alignItems: "center",
    justifyContent: "center",
    paddingHorizontal: spacing.xs,
  },
  roleBadgeText: {
    fontSize: typography.fontSize.sm,
    fontWeight: "600",
  },
});
