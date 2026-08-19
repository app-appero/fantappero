import type {
  FantasyModule,
  FantasyTurnSummary,
  LineupContext,
  LineupRole,
  LineupRosterPlayer,
  SavedLineup,
} from "@fantappero/contracts";
import {
  APPROVED_MODULES,
  MAX_AUTOMATIC_SUBSTITUTIONS,
  MAX_TACTICAL_MOVES,
  approvedModuleCatalog,
  copyPreviousLineup,
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
import {
  Breadcrumb,
  Button,
  Badge,
  Card,
  CardBody,
  CardHeader,
  FormationView,
  PageContainer,
  Select,
  UiStatePanel,
  roleBadgeVariant,
} from "@fantappero/ui";
import { useCallback, useEffect, useMemo, useState } from "react";
import { fetchFantasyTurns, fetchMyLineup, copyPreviousLineupToDraft, saveLineupDraft, saveMyLineup } from "../api/leagues";
import { getApiErrorMessage, useAuth } from "../auth/AuthContext";
import { loadStoredSession } from "../auth/sessionStorage";
import { useLocation } from "../router/simpleRouter";
import { parseWireframeStateFromSearch } from "../wireframes/useWireframeState";

const ROLE_LABEL: Record<LineupRole, string> = {
  P: "Portiere",
  D: "Difensore",
  C: "Centrocampista",
  A: "Attaccante",
};

const DEMO_ROSTER: LineupRosterPlayer[] = [
  {
    athleteId: "p1",
    athleteName: "Maignan",
    role: "P",
    slotIndex: 0,
    locked: true,
    lockLatched: true,
    kickoffAt: "2026-08-16T16:00:00.000Z",
    fixtureStatus: "PST",
  },
  { athleteId: "p2", athleteName: "Meret", role: "P", slotIndex: 1, locked: false, kickoffAt: "2026-08-15T18:30:00.000Z" },
  { athleteId: "p3", athleteName: "Donnarumma", role: "P", slotIndex: 2, locked: false, kickoffAt: "2026-08-15T18:30:00.000Z" },
  { athleteId: "d1", athleteName: "Bastoni", role: "D", slotIndex: 3, locked: false, kickoffAt: "2026-08-15T18:30:00.000Z" },
  { athleteId: "d2", athleteName: "Di Lorenzo", role: "D", slotIndex: 4, locked: false, kickoffAt: "2026-08-15T18:30:00.000Z" },
  { athleteId: "d3", athleteName: "Bremer", role: "D", slotIndex: 5, locked: false, kickoffAt: "2026-08-15T18:30:00.000Z" },
  { athleteId: "d4", athleteName: "Dumfries", role: "D", slotIndex: 6, locked: false, kickoffAt: "2026-08-15T18:30:00.000Z" },
  {
    athleteId: "d5",
    athleteName: "Acerbi",
    role: "D",
    slotIndex: 7,
    locked: true,
    kickoffAt: "2026-08-15T14:00:00.000Z",
    fixtureStatus: "1H",
  },
  { athleteId: "c1", athleteName: "Barella", role: "C", slotIndex: 8, locked: false, kickoffAt: "2026-08-15T18:30:00.000Z" },
  { athleteId: "c2", athleteName: "Koopmeiners", role: "C", slotIndex: 9, locked: false, kickoffAt: "2026-08-15T18:30:00.000Z" },
  { athleteId: "c3", athleteName: "McTominay", role: "C", slotIndex: 10, locked: false, kickoffAt: "2026-08-15T18:30:00.000Z" },
  { athleteId: "c4", athleteName: "Tonali", role: "C", slotIndex: 11, locked: false, kickoffAt: "2026-08-15T18:30:00.000Z" },
  { athleteId: "a1", athleteName: "Martinez", role: "A", slotIndex: 12, locked: false, kickoffAt: "2026-08-15T18:30:00.000Z" },
  { athleteId: "a2", athleteName: "Lookman", role: "A", slotIndex: 13, locked: false, kickoffAt: "2026-08-15T18:30:00.000Z" },
  { athleteId: "a3", athleteName: "Leao", role: "A", slotIndex: 14, locked: false, kickoffAt: "2026-08-15T18:30:00.000Z" },
  { athleteId: "a4", athleteName: "Vlahovic", role: "A", slotIndex: 15, locked: false, kickoffAt: "2026-08-15T18:30:00.000Z" },
  { athleteId: "c5", athleteName: "Locatelli", role: "C", slotIndex: 16, locked: false, kickoffAt: "2026-08-15T18:30:00.000Z" },
];

const DEMO_STARTERS = ["p1", "d1", "d2", "d3", "d4", "c1", "c2", "c3", "a1", "a2", "a3"];

const DEMO_LINEUP: SavedLineup = {
  id: "lineup-demo",
  module: "4-3-3",
  revision: 1,
  submittedAt: "2026-08-14T10:00:00.000Z",
  starters: DEMO_STARTERS.map((athleteId, index) => {
    const player = DEMO_ROSTER.find((row) => row.athleteId === athleteId);
    return {
      athleteId,
      athleteName: player?.athleteName ?? athleteId,
      role: (player?.role ?? "A") as LineupRole,
      slotKind: "starter" as const,
      sortOrder: index,
    };
  }),
  bench: ["p2", "p3", "d5", "c4", "a4", "c5"].map((athleteId, index) => {
    const player = DEMO_ROSTER.find((row) => row.athleteId === athleteId);
    return {
      athleteId,
      athleteName: player?.athleteName ?? athleteId,
      role: (player?.role ?? "P") as LineupRole,
      slotKind: "bench" as const,
      sortOrder: index,
    };
  }),
};

const DEMO_CONTEXT: LineupContext = {
  leagueId: "lega-demo",
  roundId: "turn-demo-2",
  roundNumber: 2,
  kind: "weekend",
  cutoffAt: "2026-08-15T16:00:00.000Z",
  status: "open",
  effectiveStatus: "open",
  modificationAllowed: true,
  serverNow: "2026-08-15T14:05:00.000Z",
  maxAutomaticSubstitutions: MAX_AUTOMATIC_SUBSTITUTIONS,
  maxTacticalMoves: MAX_TACTICAL_MOVES,
  tacticalMovesUsed: 0,
  tacticalMovesRemaining: MAX_TACTICAL_MOVES,
  tacticalMoves: [],
  modules: approvedModuleCatalog(),
  roster: DEMO_ROSTER,
  lineup: DEMO_LINEUP,
  previousLineup: {
    roundId: "turn-demo-1",
    roundNumber: 1,
    module: "4-3-3",
    starters: DEMO_LINEUP.starters,
    bench: DEMO_LINEUP.bench,
  },
  draft: null,
  copyAvailable: true,
  copyIssues: [],
  issues: [],
};

const DEMO_TURNS: FantasyTurnSummary[] = [
  {
    id: "turn-demo-2",
    leagueId: "lega-demo",
    number: 2,
    kind: "weekend",
    windowStartAt: "2026-08-14T22:00:00.000Z",
    windowEndAt: "2026-08-18T22:00:00.000Z",
    opensAt: null,
    closesAt: null,
    cutoffAt: "2026-08-15T16:00:00.000Z",
    status: "open",
    effectiveStatus: "open",
    skipReason: null,
    fixtureCount: 2,
    generatedAt: "2026-08-12T08:00:00.000Z",
    modificationAllowed: false,
  },
];

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

function playerName(roster: LineupRosterPlayer[], athleteId: string): string {
  return roster.find((row) => row.athleteId === athleteId)?.athleteName ?? athleteId;
}

function playerRole(roster: LineupRosterPlayer[], athleteId: string): LineupRole | null {
  return roster.find((row) => row.athleteId === athleteId)?.role ?? null;
}

function playerLocked(roster: LineupRosterPlayer[], athleteId: string, now: Date): boolean {
  const player = roster.find((row) => row.athleteId === athleteId);
  if (!player) {
    return false;
  }
  return player.locked === true || isAthleteKickoffLocked(now, player.kickoffAt, player.fixtureStatus, player.lockLatched);
}

const KICKOFF_LOCK_MESSAGE =
  "Uno o più calciatori non sono più modificabili: la loro partita è già iniziata.";

type StarterSlotOption = { value: string; label: string };

function StarterSlotField({
  label,
  role,
  value,
  options,
  disabled,
  hint,
  error,
  testId,
  placeholder,
  onSelect,
}: {
  label: string;
  role: LineupRole;
  value: string;
  options: StarterSlotOption[];
  disabled: boolean;
  hint?: string;
  error?: string;
  testId: string;
  placeholder: string;
  onSelect: (athleteId: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const selected = options.find((option) => option.value === value);
  const displayLabel = selected?.label || placeholder;

  return (
    <div className="fa-field">
      <span className="fa-field__label fa-starter-slot__label">
        <Badge variant={roleBadgeVariant(role)}>{role}</Badge>
        {label}
      </span>
      <button
        type="button"
        className="fa-select fa-starter-slot__trigger"
        data-testid={testId}
        disabled={disabled}
        aria-invalid={error ? true : undefined}
        aria-expanded={open}
        aria-haspopup="listbox"
        onClick={() => {
          if (!disabled) {
            setOpen((current) => !current);
          }
        }}
      >
        {displayLabel}
      </button>
      {open && !disabled ? (
        <ul className="fa-starter-slot__list" role="listbox" data-testid={`${testId}-options`}>
          {options.map((option) => (
            <li key={option.value}>
              <button
                type="button"
                role="option"
                aria-selected={option.value === value}
                className="fa-starter-slot__option"
                data-testid={`${testId}-option-${option.value}`}
                onClick={() => {
                  setOpen(false);
                  onSelect(option.value);
                }}
              >
                {option.label}
              </button>
            </li>
          ))}
        </ul>
      ) : null}
      {hint && !error ? <p className="fa-field__hint">{hint}</p> : null}
      {error ? (
        <p className="fa-field__error" role="alert">
          {error}
        </p>
      ) : null}
    </div>
  );
}

/** Formazione: copia precedente, bozza e tre mosse tattiche (EP06-05 / EP06-06). */
export function FormationPage() {
  const { isDemoMode, activeLeagueId, can } = useAuth();
  const { search } = useLocation();
  const demoState = isDemoMode ? parseWireframeStateFromSearch(search) : null;
  const canView = can(["roster:view"]);
  const canEdit = can(["roster:edit"]);

  const [turns, setTurns] = useState<FantasyTurnSummary[]>(() =>
    isDemoMode && demoState === "success" ? DEMO_TURNS : [],
  );
  const [selectedRoundId, setSelectedRoundId] = useState(() =>
    isDemoMode && demoState === "success" ? DEMO_CONTEXT.roundId : "",
  );
  const [context, setContext] = useState<LineupContext | null>(() =>
    isDemoMode && demoState === "success" ? DEMO_CONTEXT : null,
  );
  const [moduleCode, setModuleCode] = useState<FantasyModule>("4-3-3");
  const [starterIds, setStarterIds] = useState<string[]>(() =>
    isDemoMode && demoState === "success" ? [...DEMO_STARTERS] : starterTemplate("4-3-3").map(() => ""),
  );
  const [benchIds, setBenchIds] = useState<string[]>(() =>
    isDemoMode && demoState === "success" ? DEMO_LINEUP.bench.map((player) => player.athleteId) : [],
  );
  const [loading, setLoading] = useState(() => (isDemoMode ? demoState === "loading" : true));
  const [busy, setBusy] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(() =>
    isDemoMode && demoState === "error" ? "Impossibile caricare la formazione (demo)." : null,
  );
  const [actionError, setActionError] = useState<string | null>(null);
  const [actionMessage, setActionMessage] = useState<string | null>(null);

  const showForbidden = useMemo(() => {
    if (isDemoMode && demoState === "forbidden") {
      return true;
    }
    return !canView;
  }, [canView, demoState, isDemoMode]);

  const roster = context?.roster ?? [];
  const template = starterTemplate(moduleCode);
  const clock = context?.serverNow ? new Date(context.serverNow) : new Date();
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
  const lockedAthleteIds = roster
    .filter((row) => playerLocked(roster, row.athleteId, clock))
    .map((row) => row.athleteId);
  const clientEvaluation = evaluateLineup({
    module: moduleCode,
    starters: displayStarters.filter(Boolean).map((athleteId) => ({
      athleteId,
      role: playerRole(roster, athleteId),
    })),
    bench: displayBench.map((athleteId) => ({
      athleteId,
      role: playerRole(roster, athleteId),
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

  const load = useCallback(async () => {
    if (isDemoMode) {
      if (demoState === "loading") {
        setLoading(true);
        return;
      }
      if (demoState === "error") {
        setLoading(false);
        setLoadError("Impossibile caricare la formazione (demo).");
        setTurns([]);
        setContext(null);
        return;
      }
      if (demoState === "empty") {
        setLoading(false);
        setLoadError(null);
        setTurns([]);
        setContext(null);
        setSelectedRoundId("");
        return;
      }
      setLoading(false);
      setLoadError(null);
      setTurns(DEMO_TURNS);
      setSelectedRoundId(DEMO_CONTEXT.roundId);
      setContext(DEMO_CONTEXT);
      setModuleCode("4-3-3");
      setStarterIds([...DEMO_STARTERS]);
      setBenchIds(DEMO_LINEUP.bench.map((player) => player.athleteId));
      return;
    }

    if (!activeLeagueId) {
      setLoading(false);
      setTurns([]);
      setContext(null);
      setLoadError(null);
      return;
    }
    const session = loadStoredSession();
    if (!session?.accessToken) {
      setLoading(false);
      setLoadError("Sessione non disponibile. Accedi di nuovo.");
      return;
    }
    setLoading(true);
    setLoadError(null);
    try {
      const list = await fetchFantasyTurns(session.accessToken, activeLeagueId);
      const openTurns = list.filter(
        (turn) => turn.effectiveStatus === "open" || turn.status === "open" || turn.status === "locked",
      );
      setTurns(openTurns.length > 0 ? openTurns : list);
      const preferred =
        openTurns.find((turn) => turn.effectiveStatus === "open") ?? openTurns[0] ?? list[0];
      if (!preferred) {
        setSelectedRoundId("");
        setContext(null);
        return;
      }
      setSelectedRoundId(preferred.id);
      const detail = await fetchMyLineup(session.accessToken, activeLeagueId, preferred.id);
      setContext(detail);
      applyContext(detail);
    } catch (error) {
      setLoadError(getApiErrorMessage(error, "Impossibile caricare la formazione."));
      setTurns([]);
      setContext(null);
    } finally {
      setLoading(false);
    }
  }, [activeLeagueId, demoState, isDemoMode]);

  useEffect(() => {
    void load();
  }, [load]);

  function applyContext(detail: LineupContext) {
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

  async function selectRound(roundId: string) {
    setSelectedRoundId(roundId);
    setActionError(null);
    setActionMessage(null);
    if (isDemoMode) {
      setContext(DEMO_CONTEXT);
      applyContext(DEMO_CONTEXT);
      return;
    }
    const session = loadStoredSession();
    if (!session?.accessToken || !activeLeagueId) {
      return;
    }
    setBusy(true);
    try {
      const detail = await fetchMyLineup(session.accessToken, activeLeagueId, roundId);
      setContext(detail);
      applyContext(detail);
    } catch (error) {
      setActionError(getApiErrorMessage(error, "Formazione del turno non disponibile."));
    } finally {
      setBusy(false);
    }
  }

  function changeModule(next: FantasyModule) {
    const now = context?.serverNow ? new Date(context.serverNow) : new Date();
    const lockedIds = [
      ...new Set([
        ...starterIds.filter((id) => id && playerLocked(roster, id, now)),
        ...(context?.lineup?.starters ?? [])
          .map((player) => player.athleteId)
          .filter((id) => playerLocked(roster, id, now)),
      ]),
    ];
    const preserved = preserveLockedStarters({
      template: starterTemplate(next),
      currentStarters: [...lockedIds, ...starterIds],
      roster,
      now,
    });
    if (lockedIds.some((id) => id && !preserved.includes(id))) {
      setActionError(KICKOFF_LOCK_MESSAGE);
      return;
    }
    setModuleCode(next);
    setStarterIds(preserved);
    setBenchIds(
      orderedBenchFromRoster(
        roster.map((row) => row.athleteId),
        preserved,
        benchIds,
      ),
    );
    setActionMessage(null);
    setActionError(null);
  }

  function assignStarter(index: number, athleteId: string) {
    const reservedId = reservedIds[index] ?? "";
    if (reservedId && athleteId !== reservedId) {
      setActionError(KICKOFF_LOCK_MESSAGE);
      setStarterIds((current) => {
        const next = [...current];
        next[index] = reservedId;
        return next;
      });
      return;
    }
    if (playerLocked(roster, athleteId, clock) && athleteId !== (displayStarters[index] ?? "")) {
      setActionError(KICKOFF_LOCK_MESSAGE);
      return;
    }
    const nextStarters = [...starterIds];
    nextStarters[index] = athleteId;
    setStarterIds(nextStarters);
    setBenchIds(
      orderedBenchFromRoster(
        roster.map((row) => row.athleteId),
        nextStarters.map((value, slotIndex) => reservedIds[slotIndex] || value || ""),
        benchIds,
      ),
    );
    setActionMessage(null);
    setActionError(null);
  }

  function previousBenchIds() {
    return context?.lineup?.bench.map((player) => player.athleteId) ?? displayBench;
  }

  function moveBenchTo(fromIndex: number, toIndex: number) {
    if (fromIndex === toIndex) {
      return;
    }
    const next = moveBenchToIndex(displayBench, fromIndex, toIndex);
    const orderIssues = evaluateBenchOrderLock({
      previousBench: previousBenchIds(),
      proposedBench: next,
      lockedAthleteIds,
    });
    if (orderIssues.length > 0) {
      setActionError(orderIssues[0]?.message ?? KICKOFF_LOCK_MESSAGE);
      return;
    }
    setBenchIds(next);
    setActionError(null);
    setActionMessage(null);
  }

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
        previousBench: previousBenchIds(),
        proposedBench: next,
        lockedAthleteIds,
      }).length === 0
    );
  }

  async function save() {
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
      setActionError(lockIssues[0]?.message ?? KICKOFF_LOCK_MESSAGE);
      return;
    }
    if (tacticalEvaluation.issues.length > 0) {
      setActionError(tacticalEvaluation.issues[0]?.message ?? "Mosse tattiche esaurite.");
      return;
    }
    if (!clientEvaluation.valid) {
      setActionError(clientEvaluation.issues[0]?.message ?? "Formazione non valida.");
      return;
    }
    if (isDemoMode) {
      if (!DEMO_CONTEXT.modificationAllowed) {
        setActionError("Modifica fuori tempo: il cutoff del turno è già trascorso.");
        return;
      }
      setActionMessage(
        tacticalEvaluation.wouldConsume
          ? `Formazione salvata (demo). Mossa tattica ${movesUsed + 1}/${maxMoves} registrata.`
          : "Formazione salvata (demo).",
      );
      return;
    }
    const session = loadStoredSession();
    if (!session?.accessToken || !activeLeagueId || !selectedRoundId) {
      return;
    }
    setBusy(true);
    try {
      const detail = await saveMyLineup(session.accessToken, activeLeagueId, selectedRoundId, {
        module: moduleCode,
        starterAthleteIds: displayStarters,
        benchAthleteIds: displayBench,
      });
      setContext(detail);
      applyContext(detail);
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
    if (isDemoMode) {
      if (!DEMO_CONTEXT.modificationAllowed) {
        setActionError("Modifica fuori tempo: il cutoff del turno è già trascorso.");
        return;
      }
      const previous = DEMO_CONTEXT.previousLineup;
      if (!previous) {
        setActionError("Non c'è una formazione precedente da copiare.");
        return;
      }
      const copied = copyPreviousLineup({
        previousModule: previous.module,
        previousStarterIds: previous.starters.map((player) => player.athleteId),
        previousBenchIds: previous.bench.map((player) => player.athleteId),
        rosterAthleteIds: roster.map((row) => row.athleteId),
        lockedAthleteIds,
        currentConfirmedSlots: slotsFromLineupIds(
          context?.lineup?.starters.map((player) => player.athleteId) ?? [],
          context?.lineup?.bench.map((player) => player.athleteId) ?? [],
        ),
        currentConfirmedBench: context?.lineup?.bench.map((player) => player.athleteId) ?? [],
        roleByAthleteId: Object.fromEntries(roster.map((row) => [row.athleteId, row.role])),
      });
      if (copied.blocked) {
        setActionError(copied.issues[0]?.message ?? KICKOFF_LOCK_MESSAGE);
        return;
      }
      setModuleCode(copied.module as FantasyModule);
      setStarterIds(copied.starterIds);
      setBenchIds(copied.benchIds);
      setActionMessage(
        copied.issues.length > 0
          ? "Formazione precedente copiata in bozza (demo), rivalidata sulla rosa corrente."
          : "Formazione precedente copiata in bozza (demo).",
      );
      return;
    }
    const session = loadStoredSession();
    if (!session?.accessToken || !activeLeagueId || !selectedRoundId) {
      return;
    }
    setBusy(true);
    try {
      const detail = await copyPreviousLineupToDraft(
        session.accessToken,
        activeLeagueId,
        selectedRoundId,
      );
      setContext(detail);
      applyContext(detail);
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
      setActionError(lockIssues[0]?.message ?? KICKOFF_LOCK_MESSAGE);
      return;
    }
    const draftEvaluation = evaluateLineup({
      module: moduleCode,
      starters: displayStarters.map((athleteId) => ({
        athleteId,
        role: athleteId ? playerRole(roster, athleteId) : null,
      })),
      bench: displayBench.map((athleteId) => ({
        athleteId,
        role: playerRole(roster, athleteId),
      })),
      rosterAthleteIds: roster.map((row) => row.athleteId),
      strict: false,
    });
    if (!draftEvaluation.valid) {
      setActionError(draftEvaluation.issues[0]?.message ?? "Bozza non valida.");
      return;
    }
    if (isDemoMode) {
      if (!DEMO_CONTEXT.modificationAllowed) {
        setActionError("Modifica fuori tempo: il cutoff del turno è già trascorso.");
        return;
      }
      setActionMessage("Bozza salvata (demo). La conferma non consuma mosse tattiche.");
      return;
    }
    const session = loadStoredSession();
    if (!session?.accessToken || !activeLeagueId || !selectedRoundId) {
      return;
    }
    setBusy(true);
    try {
      const detail = await saveLineupDraft(session.accessToken, activeLeagueId, selectedRoundId, {
        module: moduleCode,
        starterAthleteIds: displayStarters,
        benchAthleteIds: displayBench,
      });
      setContext(detail);
      applyContext(detail);
      setActionMessage("Bozza salvata. Conferma la formazione quando è completa.");
    } catch (error) {
      setActionError(getApiErrorMessage(error, "Salvataggio bozza non riuscito."));
    } finally {
      setBusy(false);
    }
  }

  const pitchSlots = template.map((role, index) => {
    const athleteId = displayStarters[index] ?? "";
    return {
      id: `starter-${index}`,
      label: ROLE_LABEL[role],
      role,
      playerName: athleteId ? playerName(roster, athleteId) : "Libero",
    };
  });
  const benchSlots = displayBench.map((athleteId) => ({
    id: athleteId,
    label: playerName(roster, athleteId),
    role: playerRole(roster, athleteId) ?? "?",
    playerName: playerName(roster, athleteId),
  }));
  const maxSubs = context?.maxAutomaticSubstitutions ?? MAX_AUTOMATIC_SUBSTITUTIONS;

  const optionsForSlot = (index: number, role: LineupRole) => {
    const selected = new Set(
      displayStarters.filter((id, currentIndex) => currentIndex !== index && id),
    );
    return roster
      .filter((row) => {
        if (row.role !== role || selected.has(row.athleteId)) {
          return false;
        }
        return true;
      })
      .map((row) => ({
        value: row.athleteId,
        label: playerLocked(roster, row.athleteId, clock)
          ? `${row.athleteName} (bloccato)`
          : row.athleteName,
      }));
  };

  return (
    <PageContainer
      title="Formazione"
      header={
        <Breadcrumb
          items={[
            { label: "Leghe", href: "/leghe" },
            { label: "Formazione" },
          ]}
        />
      }
    >
      {showForbidden ? (
        <UiStatePanel
          state="forbidden"
          title="Permessi insufficienti"
          message="Non puoi modificare la formazione di questa squadra."
          testId="formation-forbidden"
        />
      ) : null}

      {!showForbidden && loading ? (
        <UiStatePanel
          state="loading"
          title="Caricamento formazione"
          message="Recupero modulo e slot disponibili…"
          testId="formation-loading"
        />
      ) : null}

      {!showForbidden && !loading && loadError ? (
        <div data-testid="formation-error-wrap">
          <UiStatePanel
            state="error"
            title="Formazione non salvata"
            message={loadError}
            testId="formation-error"
          />
          <Button type="button" variant="secondary" onClick={() => void load()}>
            Riprova
          </Button>
        </div>
      ) : null}

      {!showForbidden && !loading && !loadError && !activeLeagueId && !isDemoMode ? (
        <UiStatePanel
          state="empty"
          title="Nessuna lega attiva"
          message="Seleziona una lega per schierare la formazione."
          testId="formation-no-league"
        />
      ) : null}

      {!showForbidden && !loading && !loadError && (activeLeagueId || isDemoMode) && turns.length === 0 ? (
        <UiStatePanel
          state="empty"
          title="Formazione non impostata"
          message="Nessun turno disponibile. I turni europei si generano dal calendario della lega."
          testId="formation-empty"
        />
      ) : null}

      {!showForbidden && !loading && !loadError && context ? (
        <div data-testid="wireframe-formation-success" className="fa-ds-showcase__stack">
          <Card>
            <CardHeader title={`Turno ${context.roundNumber}`} />
            <CardBody>
              <label>
                Turno
                <select
                  value={selectedRoundId}
                  onChange={(event) => void selectRound(event.target.value)}
                  data-testid="formation-round"
                >
                  {turns.map((turn) => (
                    <option key={turn.id} value={turn.id}>
                      Turno {turn.number} ({turn.effectiveStatus === "open" ? "aperto" : turn.effectiveStatus})
                    </option>
                  ))}
                </select>
              </label>
              <p data-testid="formation-cutoff">
                Cutoff (primo kickoff): {formatDateTime(context.cutoffAt)} — lock progressivo per
                calciatore
              </p>
              <p data-testid="formation-lock-hint">
                {context.modificationAllowed
                  ? "I calciatori la cui partita è già iniziata restano bloccati anche se l'orario viene rinviato; gli altri restano modificabili."
                  : "Nessun calciatore è più modificabile."}
              </p>
              <p data-testid="formation-moves">
                Mosse tattiche: {movesUsed}/{maxMoves} usate — ne restano {movesRemaining}.
              </p>
              <p data-testid="formation-moves-hint">
                {tacticalEvaluation.wouldConsume
                  ? "Questo salvataggio consumerà 1 mossa tattica."
                  : "Questo salvataggio non consuma mosse."}{" "}
                Le sostituzioni automatiche non consumano mosse. Nessuna mossa è retroattiva sui
                calciatori bloccati.
              </p>
              {actionError ? (
                <p data-testid="formation-action-error" role="alert">
                  {actionError}
                </p>
              ) : null}
              {context.previousLineup ? (
                <p data-testid="formation-previous-hint">
                  Formazione precedente disponibile: turno {context.previousLineup.roundNumber} (
                  {context.previousLineup.module}). La copia viene rivalidata su rosa e disponibilità
                  correnti.
                </p>
              ) : (
                <p data-testid="formation-previous-empty">Nessuna formazione precedente da copiare.</p>
              )}
              {context.draft ? (
                <p data-testid="formation-draft-hint">
                  Bozza salvata
                  {context.draft.copySourceRoundNumber
                    ? ` (copiata dal turno ${context.draft.copySourceRoundNumber})`
                    : ""}
                  . Conferma per schierarla.
                </p>
              ) : null}
              {(context.copyIssues ?? []).length > 0 ? (
                <ul data-testid="formation-copy-issues">
                  {context.copyIssues?.map((issue) => (
                    <li key={`${issue.code}-${issue.message}`}>{issue.message}</li>
                  ))}
                </ul>
              ) : null}
            </CardBody>
          </Card>

          <Select
            label="Modulo"
            value={moduleCode}
            onChange={(event) => changeModule(event.target.value as FantasyModule)}
            options={APPROVED_MODULES.map((code) => {
              const moduleMeta = context.modules.find((item) => item.code === code);
              return {
                value: code,
                label: moduleMeta
                  ? `${code} (1P–${moduleMeta.defenders}D–${moduleMeta.midfielders}C–${moduleMeta.forwards}A)`
                  : code,
              };
            })}
            data-testid="formation-module"
            disabled={!context.modificationAllowed || !canEdit}
          />

          <div data-testid="formation-starters" className="fa-ds-showcase__stack">
            {template.map((role, index) => {
              const currentId = displayStarters[index] ?? "";
              const lockedSlot = Boolean(reservedIds[index]) || playerLocked(roster, currentId, clock);
              return (
                <StarterSlotField
                  key={`${moduleCode}-${index}`}
                  label={`${ROLE_LABEL[role]} ${index + 1}${lockedSlot ? " (bloccato)" : ""}`}
                  role={role}
                  value={currentId}
                  placeholder="Seleziona calciatore"
                  options={optionsForSlot(index, role)}
                  testId={`formation-starter-${index}`}
                  disabled={!context.modificationAllowed || !canEdit}
                  hint={
                    lockedSlot
                      ? "Partita già iniziata: sostituirlo con un altro calciatore viene rifiutato."
                      : undefined
                  }
                  error={
                    lockedSlot && actionError === KICKOFF_LOCK_MESSAGE
                      ? KICKOFF_LOCK_MESSAGE
                      : undefined
                  }
                  onSelect={(athleteId) => assignStarter(index, athleteId)}
                />
              );
            })}
          </div>

          <FormationView
            title={`Modulo ${moduleCode}`}
            pitchAriaLabel="Formazione titolare"
            benchAriaLabel="Panchina ordinata"
            benchTitle={`Panchina — massimo ${maxSubs} subentri`}
            maxSubstitutions={maxSubs}
            slots={pitchSlots}
            bench={benchSlots}
          />

          <div data-testid="formation-bench-order" className="fa-ds-showcase__stack">
            <p data-testid="formation-sub-hint">
              Entrano al massimo {maxSubs} panchinari, nell&apos;ordine di ingresso sotto e solo a
              parità di ruolo (P con P, D con D, C con C, A con A). Dal {maxSubs + 1}° in poi restano
              fuori se i {maxSubs} cambi sono già stati usati.
            </p>
            {displayBench.length === 0 ? (
              <p data-testid="formation-bench-empty">Nessun panchinaro: tutti i calciatori sono titolari.</p>
            ) : (
              <ol className="fa-bench-order">
                {displayBench.map((athleteId, index) => {
                  const locked = playerLocked(roster, athleteId, clock);
                  const role = playerRole(roster, athleteId);
                  const canEnter = index < maxSubs;
                  const name = playerName(roster, athleteId);
                  return (
                    <li
                      key={athleteId}
                      className={
                        canEnter ? "fa-bench-order__row" : "fa-bench-order__row fa-bench-order__row--overflow"
                      }
                    >
                      <span className="fa-bench-order__position">
                        <Select
                          className="fa-bench-order__select"
                          aria-label={`Ordine di ingresso di ${name}`}
                          value={String(index)}
                          disabled={!context.modificationAllowed || !canEdit}
                          options={displayBench.map((_, target) => ({
                            value: String(target),
                            label: `${target + 1}°`,
                            disabled: !canMoveBenchTo(index, target),
                          }))}
                          onChange={(event) => {
                            moveBenchTo(index, Number(event.target.value));
                          }}
                          data-testid={`formation-bench-position-${index}`}
                        />
                      </span>
                      <span className="fa-bench-order__player">
                        <Badge variant={roleBadgeVariant(role)}>{role ?? "?"}</Badge>
                        {name}
                        {locked ? " — bloccato" : ""}
                        <span className="fa-bench-order__hint">
                          {canEnter ? "può subentrare" : `oltre i ${maxSubs} cambi`}
                        </span>
                      </span>
                    </li>
                  );
                })}
              </ol>
            )}
          </div>

          {clientEvaluation.issues.length > 0 ? (
            <ul data-testid="formation-issues">
              {clientEvaluation.issues.map((issue) => (
                <li key={`${issue.code}-${issue.message}`}>{issue.message}</li>
              ))}
            </ul>
          ) : null}

          {actionMessage ? <p data-testid="formation-success">{actionMessage}</p> : null}

          <div className="fa-ds-showcase__stack">
            <Button
              type="button"
              variant="secondary"
              disabled={busy || !context.modificationAllowed || !canEdit || !context.copyAvailable}
              onClick={() => void copyFromPrevious()}
              data-testid="formation-copy"
            >
              Copia formazione precedente
            </Button>
            <Button
              type="button"
              variant="secondary"
              disabled={busy || !context.modificationAllowed || !canEdit}
              onClick={() => void saveDraft()}
              data-testid="formation-draft"
            >
              Salva bozza
            </Button>
            <Button
              type="button"
              variant="primary"
              disabled={
                busy ||
                !context.modificationAllowed ||
                !canEdit ||
                tacticalEvaluation.issues.length > 0
              }
              onClick={() => void save()}
              data-testid="formation-save"
            >
              Salva formazione
            </Button>
          </div>
        </div>
      ) : null}
    </PageContainer>
  );
}
