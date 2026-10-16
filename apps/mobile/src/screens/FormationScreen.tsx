import { lazyStyles } from "../theme/lazyStyles";
import type {
  AiLineupRun,
  FantasyModule,
  FantasyTeamSummary,
  FantasyTurnSummary,
  LineupContext,
  LineupRole,
} from "@fantappero/contracts";
import {
  APPROVED_MODULES,
  MAX_AUTOMATIC_SUBSTITUTIONS,
  MAX_TACTICAL_MOVES,
  blockingLineupSaveIssue,
  evaluateBenchOrderLock,
  evaluateLineup,
  evaluateProgressiveLock,
  evaluateTacticalMove,
  formatFantasyPoints,
  isAthleteKickoffLocked,
  moveBenchToIndex,
  orderedBenchFromRoster,
  preserveLockedStarters,
  labelFantasyTurnStatus,
  resolveDefaultEuropeanTurn,
  slotsFromLineupIds,
  starterTemplate,
} from "@fantappero/contracts";
import { theme } from "@fantappero/ui/theme";
import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import { AthleteName } from "../athletes/AthleteCard";
import {
  fetchFantasyTeams,
  fetchFantasyTurns,
  fetchMyLineup,
  applyBestLineup,
  copyPreviousLineupToDraft,
  runAiLineups,
  saveLineupDraft,
  saveMyLineup,
} from "../api/leagues";
import { BottomSheet, FormationPitch, PlayerPickerSheet, roleRingColor, type Candidate, type PitchSlot } from "./formation/FormationParts";
import { LockCountdown } from "../components/LockCountdown";
import { OptionPicker } from "../components/OptionPicker";
import { UiStatePanel } from "../components/UiStatePanel";
import { PageContainer } from "../layout/PageContainer";
import { useLockCountdown } from "../matchday/useLockCountdown";
import { getApiErrorMessage, useAuthSession } from "../session/DemoSessionContext";

const { colors, spacing, typography, radius } = theme;

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

const KICKOFF_LOCK_MESSAGE =
  "Uno o più calciatori non sono più modificabili: la loro partita è già iniziata.";

const AUTO_RESOLUTION_MESSAGE: Record<"draft" | "previous_round" | "zero_fallback", string> = {
  draft: "non avevi confermato una formazione: è stata usata automaticamente la bozza salvata.",
  previous_round:
    "non avevi schierato una formazione né una bozza: è stata riproposta l'ultima formazione valida.",
  zero_fallback:
    "nessuna formazione disponibile per questo turno: il punteggio fantasy è stato impostato a 0.",
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

/** Formazione: copia precedente, bozza e tre mosse tattiche (EP06-05 / EP06-06). */
export function FormationScreen() {
  const { accessToken, activeLeagueId, can } = useAuthSession();
  const canView = can(["roster:view"]);
  const canEdit = can(["roster:edit"]);
  const isAdmin = can(["league:admin"]);
  const isOperator = can(["global:operate"]);
  const canChangeTurn = isAdmin || isOperator;
  const { countdown, refetch: refetchCountdown } = useLockCountdown(accessToken, activeLeagueId);

  const [turns, setTurns] = useState<FantasyTurnSummary[]>([]);
  const [selectedRoundId, setSelectedRoundId] = useState("");
  const [teams, setTeams] = useState<FantasyTeamSummary[]>([]);
  /** Vuoto = la propria formazione. Un operatore può schierare al posto di un altro fantallenatore (EP-operatore-test). */
  const [targetTeamId, setTargetTeamId] = useState("");
  const targetTeamIdRef = useRef("");
  const lineupRequest = useRef(0);
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
  const [pickerIndex, setPickerIndex] = useState<number | null>(null);
  const [benchPickerIndex, setBenchPickerIndex] = useState<number | null>(null);
  const [toolsOpen, setToolsOpen] = useState(false);
  const [showAllBench, setShowAllBench] = useState(false);

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
    const requestId = (lineupRequest.current += 1);
    setLoading(true);
    setLoadError(null);
    try {
      const list = await fetchFantasyTurns(accessToken, activeLeagueId);
      if (lineupRequest.current !== requestId) {
        return;
      }
      setTurns(list);
      // Stesso turno di default di Turni (EP07-05): il primo non ancora
      // concluso, non una scelta propria di questa schermata — altrimenti le
      // due schermate possono aprirsi su giornate diverse.
      const preferred = resolveDefaultEuropeanTurn(list);
      if (!preferred) {
        setSelectedRoundId("");
        setContext(null);
        return;
      }
      setSelectedRoundId(preferred.id);
      const detail = await fetchMyLineup(
        accessToken,
        activeLeagueId,
        preferred.id,
        targetTeamIdRef.current || undefined,
      );
      if (lineupRequest.current !== requestId) {
        return;
      }
      setContext(detail);
      applyEditor(detail);
    } catch (error) {
      if (lineupRequest.current !== requestId) {
        return;
      }
      setLoadError(getApiErrorMessage(error, "Impossibile caricare la formazione."));
      setTurns([]);
      setContext(null);
    } finally {
      if (lineupRequest.current === requestId) {
        setLoading(false);
      }
    }
  }, [accessToken, activeLeagueId, canView]);

  useEffect(() => {
    targetTeamIdRef.current = "";
    setTargetTeamId("");
  }, [activeLeagueId]);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    if (!isOperator || !activeLeagueId || !accessToken) {
      setTeams([]);
      return;
    }
    let cancelled = false;
    void fetchFantasyTeams(accessToken, activeLeagueId)
      .then((list) => {
        if (!cancelled) {
          setTeams(list);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setTeams([]);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [accessToken, activeLeagueId, isOperator]);

  /** Admin e operatore: cambiano il turno dalla scheda Strumenti. */
  async function selectRound(roundId: string) {
    if (!accessToken || !activeLeagueId || roundId === selectedRoundId) {
      setSelectedRoundId(roundId);
      return;
    }
    const requestId = (lineupRequest.current += 1);
    setSelectedRoundId(roundId);
    setBusy(true);
    setLoadError(null);
    try {
      const detail = await fetchMyLineup(
        accessToken,
        activeLeagueId,
        roundId,
        targetTeamIdRef.current || undefined,
      );
      if (lineupRequest.current !== requestId) {
        return;
      }
      setContext(detail);
      applyEditor(detail);
      setBenchPickerIndex(null);
      setPickerIndex(null);
    } catch (error) {
      if (lineupRequest.current !== requestId) {
        return;
      }
      setLoadError(getApiErrorMessage(error, "Formazione del turno non disponibile."));
    } finally {
      if (lineupRequest.current === requestId) {
        setBusy(false);
      }
    }
  }

  /** Operatore: cambia la squadra per cui schierare, a parità di turno (EP-operatore-test). */
  async function selectTeam(teamId: string) {
    targetTeamIdRef.current = teamId;
    setTargetTeamId(teamId);
    if (!accessToken || !activeLeagueId || !selectedRoundId) {
      return;
    }
    const requestId = (lineupRequest.current += 1);
    setBusy(true);
    try {
      const detail = await fetchMyLineup(
        accessToken,
        activeLeagueId,
        selectedRoundId,
        teamId || undefined,
      );
      if (lineupRequest.current !== requestId) {
        return;
      }
      setContext(detail);
      applyEditor(detail);
    } catch (error) {
      if (lineupRequest.current !== requestId) {
        return;
      }
      setLoadError(
        getApiErrorMessage(error, "Formazione della squadra selezionata non disponibile."),
      );
    } finally {
      if (lineupRequest.current === requestId) {
        setBusy(false);
      }
    }
  }

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
  const lockMarginMinutes = context?.lineupLockMarginMinutes ?? 0;
  const playerLocked = (athleteId: string) => {
    const player = roster.find((row) => row.athleteId === athleteId);
    if (!player) {
      return false;
    }
    return (
      player.locked === true ||
      isAthleteKickoffLocked(clock, player.kickoffAt, player.fixtureStatus, player.lockLatched, lockMarginMinutes)
    );
  };
  const playerBlocked = (athleteId: string) =>
    roster.some((row) => row.athleteId === athleteId && row.selectionBlocked === true);
  const probableSuffix = (athleteId: string) => {
    const player = roster.find((row) => row.athleteId === athleteId);
    if (!player) {
      return "";
    }
    if (player.selectionBlocked || player.probableHint === "unavailable") {
      return " · out";
    }
    if (player.probableHint === "starter") {
      return " · prob.";
    }
    if (player.probableHint === "bench") {
      return " · panch.";
    }
    return "";
  };
  const playerScoreLabel = (athleteId: string): string | null => {
    const player = roster.find((row) => row.athleteId === athleteId);
    if (!player || player.fantasyScore == null) {
      return null;
    }
    const base = formatFantasyPoints(player.fantasyScore);
    return player.fixtureStatusLabel === "LIVE" ? `${base} LIVE` : base;
  };
  // `preserveLockedStarters` **ri-colloca** i bloccati nel primo slot libero
  // del loro ruolo: è ciò che serve quando cambia il modulo, ma a template
  // invariato sposterebbe un bloccato in uno slot precedente lasciandolo
  // anche in quello originale — duplicandolo in campo. Qui la formazione
  // mostrata è semplicemente la bozza, senza ri-collocazioni.
  const displayStarters = template.map((_, index) => starterIds[index] ?? "");
  const savedBench = context?.lineup?.bench.map((player) => player.athleteId) ?? [];
  const orderedBench = orderedBenchFromRoster(
    roster.map((row) => row.athleteId),
    displayStarters,
    benchIds,
  );
  const displayBench = [
    ...orderedBench.filter((athleteId) => !(playerBlocked(athleteId) && !savedBench.includes(athleteId))),
    ...orderedBench.filter((athleteId) => playerBlocked(athleteId) && !savedBench.includes(athleteId)),
  ];
  const lockedAthleteIds = roster.filter((row) => playerLocked(row.athleteId)).map((row) => row.athleteId);
  const previousBenchIds =
    context?.lineup?.bench.map((player) => player.athleteId) ?? displayBench;

  function moveBenchTo(fromIndex: number, toIndex: number): boolean {
    if (fromIndex === toIndex) {
      return true;
    }
    const next = moveBenchToIndex(displayBench, fromIndex, toIndex);
    const orderIssues = evaluateBenchOrderLock({
      previousBench: previousBenchIds,
      proposedBench: next,
      lockedAthleteIds,
    });
    if (orderIssues.length > 0) {
      setActionError(orderIssues[0]?.message ?? "Modifica fuori tempo.");
      return false;
    }
    setBenchIds(next);
    setActionError(null);
    setActionMessage(null);
    return true;
  }

  function assignBenchPlayer(slotIndex: number, athleteId: string) {
    const fromIndex = displayBench.indexOf(athleteId);
    if (fromIndex < 0) {
      return;
    }
    if (moveBenchTo(fromIndex, slotIndex)) {
      setBenchPickerIndex(null);
    }
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
  // Mosse *già usate*, non un'anteprima di quante ne resterebbero dopo un
  // salvataggio non ancora avvenuto — quella previsione resta nel solo
  // messaggio "consumerà 1 mossa tattica" mostrato altrove.
  const movesRemaining = context?.tacticalMovesRemaining ?? maxMoves - movesUsed;
  const tacticalSaveBlocked =
    blockingLineupSaveIssue({
      isPlatformOperator: isOperator,
      lockIssues: [],
      tacticalIssues: tacticalEvaluation.issues,
    }) != null;

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
    // Lock a partita iniziata e mosse esaurite bloccano il salvataggio solo
    // per chi non è operatore di piattaforma.
    const previousSlots = slotsFromLineupIds(
      context?.lineup?.starters.map((player) => player.athleteId) ?? [],
      context?.lineup?.bench.map((player) => player.athleteId) ?? [],
    );
    const saveBlock = blockingLineupSaveIssue({
      isPlatformOperator: isOperator,
      lockIssues: [
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
      ],
      tacticalIssues: tacticalEvaluation.issues,
    });
    if (saveBlock) {
      setActionError(saveBlock.message || "Modifica fuori tempo.");
      return;
    }
    if (!accessToken || !activeLeagueId || !selectedRoundId) {
      return;
    }
    setBusy(true);
    try {
      const detail = await saveMyLineup(
        accessToken,
        activeLeagueId,
        selectedRoundId,
        {
          module: moduleCode,
          starterAthleteIds: displayStarters,
          benchAthleteIds: displayBench,
        },
        targetTeamId || undefined,
      );
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
      const detail = await copyPreviousLineupToDraft(
        accessToken,
        activeLeagueId,
        selectedRoundId,
        targetTeamId || undefined,
      );
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

  async function applyBestFormation() {
    setActionError(null);
    setActionMessage(null);
    if (!accessToken || !activeLeagueId || !selectedRoundId) {
      return;
    }
    setBusy(true);
    try {
      const detail = await applyBestLineup(
        accessToken,
        activeLeagueId,
        selectedRoundId,
        targetTeamId || undefined,
      );
      setContext(detail);
      applyEditor(detail);
      setActionMessage("Formazione migliore applicata in bozza.");
    } catch (error) {
      setActionError(getApiErrorMessage(error, "Applicazione della formazione migliore non riuscita."));
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
      const detail = await saveLineupDraft(
        accessToken,
        activeLeagueId,
        selectedRoundId,
        {
          module: moduleCode,
          starterAthleteIds: displayStarters,
          benchAthleteIds: displayBench,
        },
        targetTeamId || undefined,
      );
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
          title="Formazione non caricata"
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

  const filledCount = displayStarters.filter(Boolean).length;
  const totalSlots = template.length;
  const missing = totalSlots - filledCount;
  const editable = context.modificationAllowed && canEdit;
  const maxSubs = context.maxAutomaticSubstitutions ?? MAX_AUTOMATIC_SUBSTITUTIONS;

  const pitchSlots: PitchSlot[] = template.map((role, index) => {
    const athleteId = displayStarters[index] ?? "";
    const row = roster.find((r) => r.athleteId === athleteId);
    return {
      index,
      role,
      athleteId,
      name: row ? `${row.athleteName}${probableSuffix(athleteId)}` : null,
      locked: athleteId ? playerLocked(athleteId) : false,
      scoreLabel: athleteId ? playerScoreLabel(athleteId) : null,
    };
  });

  function changeModule(code: FantasyModule) {
    // Solo la bozza corrente come fonte, mai concatenata con
    // `context.lineup.starters` — stesso motivo del calcolo di
    // `reservedIds` più sopra.
    const lockedIds = starterIds.filter((id) => id && playerLocked(id));
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
  }

  function pickPlayer(index: number, athleteId: string) {
    const currentId = displayStarters[index] ?? "";
    if (athleteId === currentId) {
      setPickerIndex(null);
      return;
    }
    // Chi occupa lo slot ha già la partita iniziata: non si tocca più.
    if (currentId && playerLocked(currentId)) {
      setActionError(KICKOFF_LOCK_MESSAGE);
      setPickerIndex(null);
      return;
    }
    if (athleteId && playerLocked(athleteId)) {
      setActionError(KICKOFF_LOCK_MESSAGE);
      setPickerIndex(null);
      return;
    }
    if (athleteId && playerBlocked(athleteId)) {
      setActionError("Questo calciatore è indisponibile e non può essere schierato titolare.");
      setPickerIndex(null);
      return;
    }
    const nextStarters = [...starterIds];
    while (nextStarters.length < totalSlots) {
      nextStarters.push("");
    }
    const otherSlot = athleteId ? nextStarters.findIndex((id, i) => id === athleteId && i !== index) : -1;
    if (otherSlot >= 0) {
      // Già titolare altrove (stesso ruolo): i due si scambiano di posto.
      nextStarters[otherSlot] = currentId;
    }
    nextStarters[index] = athleteId;
    setStarterIds(nextStarters);
    setBenchIds(
      orderedBenchFromRoster(
        roster.map((row) => row.athleteId),
        nextStarters,
        benchIds,
      ),
    );
    setActionError(null);
    setActionMessage(null);
    setPickerIndex(null);
  }

  const pickerRole = pickerIndex != null ? template[pickerIndex] : null;
  const candidates: Candidate[] =
    pickerIndex != null && pickerRole
      ? roster
          .filter((row) => row.role === pickerRole)
          .map((row) => {
            const currentId = displayStarters[pickerIndex] ?? "";
            const slotOf = displayStarters.indexOf(row.athleteId);
            const benchPos = displayBench.indexOf(row.athleteId);
            const isCurrent = row.athleteId === currentId;
            let state: Candidate["state"] = "libero";
            let stateLabel = "Libero";
            if (isCurrent) {
              state = "titolare";
              stateLabel = "Schierato qui";
            } else if (row.selectionBlocked) {
              state = "bloccato";
              stateLabel = row.probableNote ?? "Indisponibile";
            } else if (playerLocked(row.athleteId)) {
              state = "bloccato";
              stateLabel = "Bloccato · partita iniziata";
            } else if (slotOf >= 0) {
              state = "titolare";
              stateLabel = `Schierato in ${pickerRole} ${slotOf + 1}`;
            } else if (benchPos >= 0) {
              state = "panchina";
              stateLabel = `In panchina · ${benchPos + 1}°`;
            } else if (row.probableHint === "starter") {
              stateLabel = "Titolare probabile";
            } else if (row.probableHint === "bench") {
              stateLabel = "Panchina probabile";
            }
            return {
              athleteId: row.athleteId,
              name: row.athleteName,
              state,
              stateLabel,
              scoreLabel: playerScoreLabel(row.athleteId),
              current: isCurrent,
            };
          })
      : [];

  const panchinaIds = displayBench.slice(0, maxSubs);
  const tribunaIds = displayBench.slice(maxSubs);
  const benchCandidates: Candidate[] =
    benchPickerIndex != null
      ? roster
          .filter((row) => !displayStarters.includes(row.athleteId))
          .map((row) => {
            const benchPos = displayBench.indexOf(row.athleteId);
            const isCurrent = benchPos === benchPickerIndex;
            const locked = playerLocked(row.athleteId);
            let state: Candidate["state"] = "libero";
            let stateLabel = "Disponibile";
            if (isCurrent) {
              state = "panchina";
              stateLabel = "Schierato qui";
            } else if (row.selectionBlocked) {
              state = "bloccato";
              stateLabel = row.probableNote ?? "Indisponibile";
            } else if (locked) {
              state = "bloccato";
              stateLabel = "Bloccato · partita iniziata";
            } else if (benchPos >= 0 && benchPos < maxSubs) {
              state = "panchina";
              stateLabel = `In panchina · ${benchPos + 1}°`;
            } else {
              stateLabel = row.probableHint === "bench" ? "Panchina probabile" : "In tribuna";
            }
            return {
              athleteId: row.athleteId,
              name: row.athleteName,
              role: row.role,
              state,
              stateLabel,
              scoreLabel: playerScoreLabel(row.athleteId),
              current: isCurrent,
            };
          })
      : [];
  const toolDisabled = busy || !editable;

  return (
    <PageContainer title="Formazione">
      <View style={styles.content}>
        <View style={styles.statusRow}>
          <Text style={styles.turnTitle} testID="formation-cutoff">
            Turno {context.roundNumber} · cutoff {formatDateTime(context.cutoffAt)}
          </Text>
          <View style={styles.movesChip}>
            <Text style={styles.movesText} testID="formation-moves">
              Mosse {movesUsed}/{maxMoves}
            </Text>
          </View>
        </View>
        {countdown && countdown.roundId === context.roundId ? (
          <LockCountdown
            state={countdown.state}
            nextLockAt={countdown.nextLockAt}
            onExpire={refetchCountdown}
            testID="formation-lock-countdown"
          />
        ) : null}
        {!context.modificationAllowed ? (
          <Text style={styles.meta} testID="formation-lock-hint">
            Nessun calciatore è più modificabile.
          </Text>
        ) : null}
        {context.lineup?.systemGeneratedAi ? (
          <Text style={styles.meta} testID="formation-ai-badge">
            Gestita automaticamente — formazione scelta dall'automazione IA
            {context.lineup.aiDecidedAt ? ` il ${formatDateTime(context.lineup.aiDecidedAt)}` : ""}
            {context.lineup.aiAlgorithmVersion ? ` · ${context.lineup.aiAlgorithmVersion}` : ""}.
          </Text>
        ) : null}
        {context.lineup?.autoResolutionSource ? (
          <Text style={styles.meta} testID="formation-auto-resolution-badge">
            Formazione applicata automaticamente —{" "}
            {AUTO_RESOLUTION_MESSAGE[context.lineup.autoResolutionSource]}
          </Text>
        ) : null}
        {context.draft ? (
          <Text style={styles.meta} testID="formation-draft-hint">
            Bozza salvata
            {context.draft.copySourceRoundNumber
              ? ` (copiata dal turno ${context.draft.copySourceRoundNumber})`
              : ""}
            .
          </Text>
        ) : null}
        {context.teamName ? (
          <Text style={styles.teamName} testID="formation-team-name">
            {context.teamName}
          </Text>
        ) : null}

        <View style={styles.modules} testID="formation-module">
          {APPROVED_MODULES.map((code) => (
            <Pressable
              key={code}
              accessibilityRole="button"
              disabled={!editable}
              onPress={() => changeModule(code)}
              style={[styles.pill, moduleCode === code ? styles.pillActive : null]}
            >
              <Text
                style={[styles.pillText, moduleCode === code ? styles.pillTextActive : null]}
                numberOfLines={1}
                adjustsFontSizeToFit
                minimumFontScale={0.7}
              >
                {code}
              </Text>
            </Pressable>
          ))}
        </View>

        <View style={styles.progressHead}>
          <View style={styles.progressTitle}>
            <Text style={styles.progressLabel}>Titolari</Text>
            <Text style={[styles.progressCount, missing === 0 ? styles.progressOk : null]}>
              {filledCount}/{totalSlots}
            </Text>
          </View>
          <Text style={styles.progressHint} numberOfLines={2}>
            {missing === 0 ? "Formazione completa" : "Tocca un cerchio per scegliere"}
          </Text>
        </View>
        <View style={styles.progressTrack}>
          <View
            style={[
              styles.progressFill,
              missing === 0 ? styles.progressFillOk : null,
              { width: `${Math.round((filledCount / Math.max(totalSlots, 1)) * 100)}%` as `${number}%` },
            ]}
          />
        </View>

        {filledCount === 0 && editable ? (
          <View style={styles.startCard} testID="formation-start-card">
            <Text style={styles.startTitle}>Parti da una base</Text>
            <Text style={styles.meta}>
              Compila la formazione in un tocco, poi ritocca gli slot che vuoi cambiare.
            </Text>
            <View style={styles.startRow}>
              <Pressable
                accessibilityRole="button"
                disabled={toolDisabled}
                onPress={() => void applyBestFormation()}
                style={[styles.startButton, styles.startButtonPrimary, toolDisabled ? styles.disabled : null]}
                testID="formation-apply-best"
              >
                <Text style={styles.startButtonLabel} numberOfLines={1} adjustsFontSizeToFit minimumFontScale={0.75}>
                  Formazione migliore
                </Text>
              </Pressable>
              <Pressable
                accessibilityRole="button"
                disabled={toolDisabled || !context.copyAvailable}
                onPress={() => void copyFromPrevious()}
                style={[
                  styles.startButton,
                  toolDisabled || !context.copyAvailable ? styles.disabled : null,
                ]}
                testID="formation-copy"
              >
                <Text
                  style={styles.startButtonLabelSecondary}
                  numberOfLines={1}
                  adjustsFontSizeToFit
                  minimumFontScale={0.75}
                >
                  {context.previousLineup ? `Copia turno ${context.previousLineup.roundNumber}` : "Copia precedente"}
                </Text>
              </Pressable>
            </View>
          </View>
        ) : null}

        <FormationPitch
          slots={pitchSlots}
          selectedIndex={pickerIndex}
          disabled={!editable && filledCount === 0}
          onSlotPress={(index) => {
            if (!editable) {
              const id = displayStarters[index];
              if (id) {
                setActionError(null);
              }
              return;
            }
            setPickerIndex(index);
          }}
        />
        {roster.some((row) => row.probableHint) ? (
          <Text style={styles.meta} testID="formation-probable-hint">
            I titolari probabili sono segnati nel campo. Gli indisponibili non si possono schierare.
          </Text>
        ) : null}

        <View style={styles.benchHead}>
          <Text style={styles.sectionTitle}>Panchina</Text>
          <Text style={styles.meta} testID="formation-sub-hint">
            Entrano al massimo {maxSubs} panchinari, nell'ordine e solo a parità di ruolo. Tocca Cambia
            per scegliere chi inserire: i tab filtrano per ruolo. Il nome apre la scheda.
          </Text>
        </View>
        {displayBench.length === 0 ? (
          <Text style={styles.meta} testID="formation-bench-empty">
            Nessun panchinaro: tutti i calciatori sono titolari.
          </Text>
        ) : (
          <View style={styles.benchList} testID="formation-bench-order">
            {panchinaIds.map((id, index) => {
              const row = roster.find((r) => r.athleteId === id);
              const name = row?.athleteName ?? id;
              const role = row?.role ?? "?";
              const locked = playerLocked(id);
              return (
                <View
                  key={id}
                  style={[styles.benchRow, benchPickerIndex === index ? styles.benchRowSelected : null]}
                  testID={`formation-bench-${index}`}
                >
                  <Text style={styles.benchOrder}>{index + 1}°</Text>
                  <View style={[styles.benchRole, { backgroundColor: roleRingColor(role) }]}>
                    <Text style={styles.benchRoleText}>{role}</Text>
                  </View>
                  <View style={styles.benchBody}>
                    <AthleteName plain athleteId={id} style={styles.benchName}>
                      {name}
                    </AthleteName>
                    <Text style={styles.meta}>
                      {locked ? "Bloccato · " : ""}
                      può subentrare
                      {playerScoreLabel(id) ? ` · ${playerScoreLabel(id)}` : ""}
                    </Text>
                  </View>
                  {editable ? (
                    <Pressable
                      accessibilityRole="button"
                      accessibilityLabel={`Cambia ${name}, ${index + 1}° in panchina`}
                      onPress={() => setBenchPickerIndex(index)}
                      style={styles.benchChange}
                      testID={`formation-bench-change-${index}`}
                    >
                      <Text style={styles.benchChangeLabel}>Cambia</Text>
                    </Pressable>
                  ) : null}
                </View>
              );
            })}
            {tribunaIds.length > 0 ? (
              <Pressable
                accessibilityRole="button"
                onPress={() => setShowAllBench((v) => !v)}
                style={styles.moreBench}
                testID="formation-bench-toggle"
              >
                <Text style={styles.meta}>
                  {showAllBench
                    ? "Nascondi la tribuna"
                    : `Altri ${tribunaIds.length} in tribuna: restano fuori`}
                </Text>
                <Text style={styles.link}>{showAllBench ? "Nascondi" : "Mostra"}</Text>
              </Pressable>
            ) : null}
            {showAllBench
              ? tribunaIds.map((id, offset) => {
                  const index = maxSubs + offset;
                  const row = roster.find((r) => r.athleteId === id);
                  const name = row?.athleteName ?? id;
                  const role = row?.role ?? "?";
                  return (
                    <View
                      key={id}
                      style={[styles.benchRow, styles.benchOverflow]}
                      testID={`formation-bench-${index}`}
                    >
                      <Text style={styles.benchOrder}>{index + 1}°</Text>
                      <View style={[styles.benchRole, { backgroundColor: roleRingColor(role) }]}>
                        <Text style={styles.benchRoleText}>{role}</Text>
                      </View>
                      <View style={styles.benchBody}>
                        <AthleteName plain athleteId={id} style={styles.benchName}>
                          {name}
                        </AthleteName>
                        <Text style={styles.meta}>oltre i {maxSubs} cambi</Text>
                      </View>
                    </View>
                  );
                })
              : null}
          </View>
        )}

        {actionError ? (
          <Text style={[styles.error, styles.banner]} testID="formation-action-error">
            {actionError}
          </Text>
        ) : null}
        {evaluation.issues.length > 0 ? (
          <View style={styles.banner}>
            {evaluation.issues.map((issue) => (
              <Text key={`${issue.code}-${issue.message}`} style={styles.error}>
                • {issue.message}
              </Text>
            ))}
          </View>
        ) : null}
        {actionMessage ? (
          <Text style={[styles.ok, styles.bannerOk]} testID="formation-success">
            {actionMessage}
          </Text>
        ) : null}

        <View style={styles.actionBar}>
          <Pressable
            accessibilityRole="button"
            accessibilityLabel="Strumenti"
            onPress={() => setToolsOpen(true)}
            style={styles.moreButton}
            testID="formation-tools"
          >
            <Text style={styles.moreText}>•••</Text>
          </Pressable>
          <Pressable
            accessibilityRole="button"
            disabled={toolDisabled}
            onPress={() => void saveDraft()}
            style={[styles.draftButton, toolDisabled ? styles.disabled : null]}
            testID="formation-draft"
          >
            <Text style={styles.buttonSecondaryLabel}>Bozza</Text>
          </Pressable>
          <Pressable
            accessibilityRole="button"
            disabled={toolDisabled || missing > 0 || tacticalSaveBlocked}
            onPress={() => void save()}
            style={[
              styles.saveButton,
              toolDisabled || missing > 0 || tacticalSaveBlocked ? styles.saveDisabled : null,
            ]}
            testID="formation-save"
          >
            <Text style={styles.buttonLabel}>
              {missing > 0 ? `Mancano ${missing} titolari` : "Salva formazione"}
            </Text>
          </Pressable>
        </View>
      </View>

      <PlayerPickerSheet
        key={pickerIndex ?? "closed"}
        visible={pickerIndex != null && pickerRole != null}
        role={pickerRole ?? "P"}
        slotNumber={(pickerIndex ?? 0) + 1}
        moduleCode={moduleCode}
        candidates={candidates}
        hasCurrent={pickerIndex != null && Boolean(displayStarters[pickerIndex])}
        onPick={(athleteId) => pickerIndex != null && pickPlayer(pickerIndex, athleteId)}
        onClear={() => pickerIndex != null && pickPlayer(pickerIndex, "")}
        onClose={() => setPickerIndex(null)}
      />

      <PlayerPickerSheet
        key={benchPickerIndex ?? "bench-closed"}
        visible={benchPickerIndex != null}
        role={
          roster.find((row) => row.athleteId === panchinaIds[benchPickerIndex ?? -1])?.role ?? "C"
        }
        slotNumber={(benchPickerIndex ?? 0) + 1}
        moduleCode={moduleCode}
        title={`Panchina ${(benchPickerIndex ?? 0) + 1}°`}
        subtitle="Scegli chi inserire in questo posto"
        candidates={benchCandidates}
        hasCurrent={false}
        showRoleTabs
        onPick={(athleteId) => benchPickerIndex != null && assignBenchPlayer(benchPickerIndex, athleteId)}
        onClear={() => setBenchPickerIndex(null)}
        onClose={() => setBenchPickerIndex(null)}
      />

      <BottomSheet
        visible={toolsOpen}
        title="Strumenti"
        onClose={() => setToolsOpen(false)}
        testID="formation-tools-sheet"
      >
        <ScrollView contentContainerStyle={styles.toolsBody}>
          {canChangeTurn && turns.length > 0 ? (
            <View style={styles.tool} testID="formation-round-tool">
              <Text style={styles.toolTitle}>Cambia turno</Text>
              <OptionPicker
                label="Turno"
                options={turns.map((turn) => ({
                  value: turn.id,
                  label: `Turno ${turn.number} (${labelFantasyTurnStatus(turn.effectiveStatus)})`,
                }))}
                value={selectedRoundId}
                onChange={(roundId) => {
                  setToolsOpen(false);
                  void selectRound(roundId);
                }}
                testID="formation-round"
              />
            </View>
          ) : null}
          {isOperator && teams.length > 0 ? (
            <View style={styles.tool}>
              <Text style={styles.toolTitle}>Schiera per un altro fantallenatore</Text>
              <View style={styles.row}>
                <Pressable
                  accessibilityRole="button"
                  disabled={busy || loading}
                  onPress={() => void selectTeam("")}
                  style={[styles.chip, targetTeamId === "" ? styles.chipActive : null]}
                  testID="formation-team-self"
                >
                  <Text style={styles.chipLabel}>La mia squadra</Text>
                </Pressable>
                {teams.map((team) => (
                  <Pressable
                    key={team.id}
                    accessibilityRole="button"
                    disabled={busy || loading}
                    onPress={() => void selectTeam(team.id)}
                    style={[styles.chip, targetTeamId === team.id ? styles.chipActive : null]}
                    testID={`formation-team-${team.id}`}
                  >
                    <Text style={styles.chipLabel}>{team.name}</Text>
                  </Pressable>
                ))}
              </View>
            </View>
          ) : null}
          <Pressable
            accessibilityRole="button"
            disabled={toolDisabled || !context.copyAvailable}
            onPress={() => {
              setToolsOpen(false);
              void copyFromPrevious();
            }}
            style={[styles.tool, toolDisabled || !context.copyAvailable ? styles.disabled : null]}
            testID="formation-copy-tool"
          >
            <Text style={styles.toolTitle}>Copia formazione precedente</Text>
            <Text style={styles.meta} testID="formation-previous-hint">
              {context.previousLineup
                ? `Turno ${context.previousLineup.roundNumber} · ${context.previousLineup.module}. Viene rivalidata su rosa e disponibilità correnti.`
                : "Nessuna formazione precedente da copiare."}
            </Text>
          </Pressable>
          <Pressable
            accessibilityRole="button"
            disabled={toolDisabled}
            onPress={() => {
              setToolsOpen(false);
              void applyBestFormation();
            }}
            style={[styles.tool, toolDisabled ? styles.disabled : null]}
            testID="formation-apply-best-tool"
          >
            <Text style={styles.toolTitle}>Applica formazione migliore</Text>
            <Text style={styles.meta}>Sceglie i titolari con il punteggio atteso più alto.</Text>
          </Pressable>
          {isAdmin ? (
            <View style={styles.tool} testID="formation-ai-admin">
              <Text style={styles.toolTitle}>Formazioni IA</Text>
              <Text style={styles.meta}>
                Genera automaticamente la formazione delle sole squadre controllate da un fantallenatore IA
                per questo turno. Non tocca mai le formazioni schierate a mano da un umano.
              </Text>
              <View style={styles.row}>
                <Pressable
                  style={[styles.startButton, aiLineupBusy ? styles.disabled : null]}
                  disabled={aiLineupBusy}
                  onPress={() => void runAiLineupsAction(true)}
                  testID="formation-ai-preview"
                >
                  <Text style={styles.buttonSecondaryLabel}>Anteprima</Text>
                </Pressable>
                <Pressable
                  style={[styles.startButton, styles.startButtonPrimary, aiLineupBusy ? styles.disabled : null]}
                  disabled={aiLineupBusy}
                  onPress={() => void runAiLineupsAction(false)}
                  testID="formation-ai-regenerate"
                >
                  <Text style={styles.buttonLabel}>Rigenera</Text>
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
          <Text style={styles.meta} testID="formation-moves-hint">
            {tacticalEvaluation.wouldConsume
              ? "Questo salvataggio consumerà 1 mossa tattica."
              : "Questo salvataggio non consuma mosse."}{" "}
            Le sostituzioni automatiche non consumano mosse. Mosse tattiche: {movesUsed}/{maxMoves} usate — ne
            restano {movesRemaining}.
          </Text>
          <Text style={styles.meta}>
            I calciatori la cui partita è già iniziata restano bloccati anche se l'orario viene rinviato; gli
            altri restano modificabili.
          </Text>
        </ScrollView>
      </BottomSheet>
    </PageContainer>
  );
}

const styles = lazyStyles(() => StyleSheet.create({
  content: {
    gap: spacing.sm,
    paddingBottom: spacing.xl,
  },
  statusRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: spacing.sm,
  },
  turnTitle: {
    flex: 1,
    color: colors.foreground,
    fontSize: typography.fontSize.md,
    fontWeight: "700",
  },
  movesChip: {
    borderRadius: radius.pill,
    borderWidth: 1,
    borderColor: colors.brand,
    paddingHorizontal: spacing.sm,
    paddingVertical: 2,
  },
  movesText: { color: colors.foreground, fontSize: typography.fontSize.sm, fontWeight: "600" },
  meta: {
    color: colors.foregroundMuted,
    fontSize: typography.fontSize.sm,
  },
  teamName: { color: colors.foregroundMuted, fontWeight: "600" },
  body: {
    color: colors.foreground,
    fontSize: typography.fontSize.md,
  },
  row: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacing.xs,
  },
  modules: {
    flexDirection: "row",
    alignItems: "center",
    gap: 4,
  },
  pill: {
    flex: 1,
    minWidth: 0,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.pill,
    paddingHorizontal: 2,
    paddingVertical: 8,
    minHeight: 36,
    alignItems: "center",
    justifyContent: "center",
  },
  pillActive: { backgroundColor: colors.brand, borderColor: colors.brand },
  pillText: {
    color: colors.foreground,
    fontWeight: "700",
    fontSize: typography.fontSize.xs,
    textAlign: "center",
  },
  pillTextActive: { color: colors.onBrand },
  progressHead: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: spacing.sm,
  },
  progressTitle: {
    flexDirection: "row",
    alignItems: "baseline",
    flexShrink: 0,
    gap: 6,
  },
  progressLabel: { color: colors.foreground, fontWeight: "600" },
  progressCount: {
    fontSize: typography.fontSize.xl,
    fontStyle: "italic",
    fontWeight: "800",
    paddingRight: 6,
  },
  progressHint: {
    flex: 1,
    flexShrink: 1,
    textAlign: "right",
    color: colors.foregroundMuted,
    fontSize: typography.fontSize.sm,
  },
  progressOk: { color: colors.success },
  progressTrack: {
    height: 6,
    borderRadius: 999,
    backgroundColor: colors.border,
    overflow: "hidden",
  },
  progressFill: { height: 6, borderRadius: 999, backgroundColor: colors.brand },
  progressFillOk: { backgroundColor: colors.success },
  startCard: {
    gap: spacing.xs,
    borderWidth: 1,
    borderColor: colors.brand,
    borderRadius: radius.lg,
    backgroundColor: colors.backgroundElevated,
    padding: spacing.md,
  },
  startTitle: { color: colors.foreground, fontWeight: "700", fontSize: typography.fontSize.md },
  startRow: {
    flexDirection: "row",
    flexWrap: "nowrap",
    alignItems: "center",
    gap: spacing.xs,
  },
  startButton: {
    flexGrow: 1,
    flexShrink: 1,
    flexBasis: 0,
    minWidth: 0,
    minHeight: 44,
    alignItems: "center",
    justifyContent: "center",
    borderRadius: radius.pill,
    borderWidth: 1,
    borderColor: colors.border,
    paddingHorizontal: spacing.xs,
  },
  startButtonLabel: {
    color: colors.onBrand,
    fontWeight: "600",
    fontSize: typography.fontSize.sm,
    textAlign: "center",
  },
  startButtonLabelSecondary: {
    color: colors.foreground,
    fontWeight: "600",
    fontSize: typography.fontSize.sm,
    textAlign: "center",
  },
  startButtonPrimary: { backgroundColor: colors.brand, borderColor: colors.brand },
  benchHead: { gap: 2, marginTop: spacing.sm },
  sectionTitle: {
    color: colors.foreground,
    fontSize: typography.fontSize.xl,
    fontStyle: "italic",
    fontWeight: "800",
    textTransform: "uppercase",
  },
  benchList: { gap: spacing.xs },
  benchRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.lg,
    backgroundColor: colors.backgroundElevated,
    padding: spacing.sm,
  },
  benchOverflow: { opacity: 0.65 },
  benchRowSelected: { borderColor: colors.accent },
  benchOrder: {
    width: 30,
    color: colors.accent,
    fontSize: typography.fontSize.lg,
    fontStyle: "italic",
    fontWeight: "800",
  },
  benchRole: { width: 30, height: 30, borderRadius: 15, alignItems: "center", justifyContent: "center" },
  benchRoleText: { color: "#11162B", fontWeight: "800", fontStyle: "italic" },
  benchBody: { flex: 1, minWidth: 0 },
  benchName: { color: colors.foreground, fontSize: typography.fontSize.md, fontWeight: "700" },
  benchChange: {
    minHeight: 36,
    paddingHorizontal: spacing.sm,
    borderRadius: radius.pill,
    borderWidth: 2,
    borderColor: colors.accent,
    backgroundColor: colors.brand,
    alignItems: "center",
    justifyContent: "center",
  },
  benchChangeLabel: {
    color: colors.onBrand,
    fontWeight: "800",
    fontSize: typography.fontSize.sm,
  },
  moreBench: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    padding: spacing.sm,
    borderRadius: radius.lg,
    borderWidth: 1,
    borderColor: colors.border,
  },
  link: { color: colors.accent, fontWeight: "600" },
  chip: {
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.pill,
    paddingHorizontal: spacing.sm,
    paddingVertical: spacing.xs,
  },
  chipActive: { borderColor: colors.brand, borderWidth: 2 },
  chipLabel: { color: colors.foreground, fontSize: typography.fontSize.sm },
  button: {
    backgroundColor: colors.brand,
    borderRadius: radius.pill,
    padding: spacing.sm,
    alignItems: "center",
    marginTop: spacing.sm,
  },
  buttonLabel: { color: colors.onBrand, fontWeight: "600" },
  buttonSecondaryLabel: { color: colors.foreground, fontWeight: "600" },
  disabled: { opacity: 0.5 },
  error: { color: colors.danger },
  ok: { color: colors.success },
  banner: {
    borderWidth: 1,
    borderColor: colors.danger,
    borderRadius: radius.md,
    padding: spacing.sm,
    gap: 4,
    overflow: "hidden",
  },
  bannerOk: {
    borderWidth: 1,
    borderColor: colors.success,
    borderRadius: radius.md,
    padding: spacing.sm,
    overflow: "hidden",
  },
  actionBar: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.xs,
    padding: spacing.sm,
    borderRadius: 26,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.backgroundElevated,
    marginTop: spacing.sm,
  },
  moreButton: {
    width: 48,
    height: 48,
    borderRadius: 24,
    borderWidth: 1,
    borderColor: colors.border,
    alignItems: "center",
    justifyContent: "center",
  },
  moreText: { color: colors.foreground, fontWeight: "800", letterSpacing: 1 },
  draftButton: {
    minHeight: 48,
    paddingHorizontal: spacing.md,
    borderRadius: radius.pill,
    borderWidth: 1,
    borderColor: colors.border,
    alignItems: "center",
    justifyContent: "center",
  },
  saveButton: {
    flex: 1,
    minHeight: 48,
    borderRadius: radius.pill,
    backgroundColor: colors.brand,
    alignItems: "center",
    justifyContent: "center",
  },
  saveDisabled: { backgroundColor: colors.border },
  toolsBody: { gap: spacing.sm, paddingBottom: spacing.md },
  tool: {
    gap: spacing.xs,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.lg,
    padding: spacing.md,
  },
  toolTitle: { color: colors.foreground, fontWeight: "700", fontSize: typography.fontSize.md },
}));
