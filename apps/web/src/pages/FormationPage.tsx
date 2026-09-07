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
  fantasyBadgesFromBonusMalus,
  formatFantasyPoints,
  isAthleteKickoffLocked,
  layoutFromModule,
  lineupSignature,
  moveBenchToIndex,
  orderedBenchFromRoster,
  preserveLockedStarters,
  resolveDefaultEuropeanTurn,
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
  FootballPitch,
  PageContainer,
  Select,
  UiStatePanel,
  roleBadgeVariant,
  useToast,
  type PitchPlayer,
} from "@fantappero/ui";
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  fetchFantasyTurns,
  fetchMyLineup,
  applyBestLineup,
  copyPreviousLineupToDraft,
  saveLineupDraft,
  saveMyLineup,
} from "../api/leagues";
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
  systemGeneratedAi: false,
  aiAlgorithmVersion: null,
  aiDecidedAt: null,
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
  lineupLockMarginMinutes: 15,
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
    matchStatus: "scheduled",
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

function playerPhotoUrl(roster: LineupRosterPlayer[], athleteId: string): string | null {
  return roster.find((row) => row.athleteId === athleteId)?.photoUrl ?? null;
}

/** `"7.5"`, `"7.5 LIVE"` mentre la partita reale è in corso, o `null` se non ancora giocata. */
function playerScoreLabel(roster: LineupRosterPlayer[], athleteId: string): string | null {
  const player = roster.find((row) => row.athleteId === athleteId);
  if (!player || player.fantasyScore == null) {
    return null;
  }
  const base = formatFantasyPoints(player.fantasyScore);
  return player.fixtureStatusLabel === "LIVE" ? `${base} LIVE` : base;
}

function playerBadges(roster: LineupRosterPlayer[], athleteId: string) {
  const player = roster.find((row) => row.athleteId === athleteId);
  return fantasyBadgesFromBonusMalus(player?.bonusMalus ?? []);
}

function playerLocked(
  roster: LineupRosterPlayer[],
  athleteId: string,
  now: Date,
  marginMinutes = 0,
): boolean {
  const player = roster.find((row) => row.athleteId === athleteId);
  if (!player) {
    return false;
  }
  return (
    player.locked === true ||
    isAthleteKickoffLocked(now, player.kickoffAt, player.fixtureStatus, player.lockLatched, marginMinutes)
  );
}

const KICKOFF_LOCK_MESSAGE =
  "Uno o più calciatori non sono più modificabili: la loro partita è già iniziata.";

const AUTO_RESOLUTION_MESSAGE: Record<"draft" | "previous_round" | "zero_fallback", string> = {
  draft: "Non avevi confermato una formazione: è stata usata automaticamente la bozza salvata.",
  previous_round:
    "Non avevi schierato una formazione né una bozza: è stata riproposta l'ultima formazione valida.",
  zero_fallback:
    "Nessuna formazione disponibile per questo turno: il punteggio fantasy è stato impostato a 0.",
};

type StarterSlotOption = { value: string; label: string };

function StarterSlotField({
  label,
  role,
  value,
  options,
  disabled,
  hint,
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
      {hint ? <p className="fa-field__hint">{hint}</p> : null}
    </div>
  );
}

function BenchOrderRow({
  athleteId,
  index,
  canEnter,
  maxSubs,
  name,
  role,
  locked,
  disabled,
  options,
  onMove,
  scoreLabel,
}: {
  athleteId: string;
  index: number;
  canEnter: boolean;
  maxSubs: number;
  name: string;
  role: LineupRole | null;
  locked: boolean;
  disabled: boolean;
  options: Array<{ value: string; label: string; disabled: boolean }>;
  onMove: (target: number) => void;
  scoreLabel?: string | null;
}) {
  return (
    <li
      key={athleteId}
      className={canEnter ? "fa-bench-order__row" : "fa-bench-order__row fa-bench-order__row--overflow"}
    >
      <span className="fa-bench-order__position">
        <Select
          className="fa-bench-order__select"
          aria-label={`Ordine di ingresso di ${name}`}
          value={String(index)}
          disabled={disabled}
          options={options}
          onChange={(event) => onMove(Number(event.target.value))}
          data-testid={`formation-bench-position-${index}`}
        />
      </span>
      <span className="fa-bench-order__player">
        <Badge variant={roleBadgeVariant(role)}>{role ?? "?"}</Badge>
        {name}
        {locked ? " — bloccato" : ""}
        {scoreLabel ? (
          <strong
            className="fa-bench-order__score"
            data-testid={`formation-bench-score-${athleteId}`}
          >
            {" "}
            {scoreLabel}
          </strong>
        ) : null}
        <span className="fa-bench-order__hint">
          {canEnter ? "può subentrare" : `oltre i ${maxSubs} cambi`}
        </span>
      </span>
    </li>
  );
}

/** Formazione: copia precedente, bozza e tre mosse tattiche (EP06-05 / EP06-06). */
export function FormationPage() {
  const { isDemoMode, activeLeagueId, can } = useAuth();
  const { search } = useLocation();
  const demoState = isDemoMode ? parseWireframeStateFromSearch(search) : null;
  const canView = can(["roster:view"]);
  const canEdit = can(["roster:edit"]);
  const { push: pushToast } = useToast();

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

  const showForbidden = useMemo(() => {
    if (isDemoMode && demoState === "forbidden") {
      return true;
    }
    return !canView;
  }, [canView, demoState, isDemoMode]);

  const roster = context?.roster ?? [];
  const lockMarginMinutes = context?.lineupLockMarginMinutes ?? 0;
  const template = starterTemplate(moduleCode);
  const clock = context?.serverNow ? new Date(context.serverNow) : new Date();
  // Solo la bozza/stato mostrato a schermo: mai concatenato con
  // `context.lineup.starters` (l'ultima formazione confermata), che può
  // legittimamente differire dalla bozza (es. dopo "Applica formazione
  // migliore") e riservare un bloccato in uno slot diverso da quello già
  // corretto assegnato dal server — duplicando o svuotando uno slot.
  // `preserveLockedStarters` **ri-colloca** i bloccati nel primo slot libero
  // del loro ruolo: è ciò che serve quando cambia il modulo, ma a template
  // invariato sposterebbe un bloccato in uno slot precedente lasciandolo
  // anche in quello originale — duplicandolo in campo. Qui la formazione
  // mostrata è semplicemente la bozza, senza ri-collocazioni.
  const displayStarters = template.map((_, index) => starterIds[index] ?? "");
  const displayBench = orderedBenchFromRoster(
    roster.map((row) => row.athleteId),
    displayStarters,
    benchIds,
  );
  const lockedAthleteIds = roster
    .filter((row) => playerLocked(roster, row.athleteId, clock, lockMarginMinutes))
    .map((row) => row.athleteId);

  // Ruolo con cui il calciatore è stato effettivamente schierato nella
  // formazione confermata. Per chi è già bloccato vale questo, non il ruolo
  // ricalcolato oggi dal listone: una riclassificazione a stagione in corso
  // non deve invalidare a posteriori una formazione legittima che ormai non
  // è più modificabile. Stessa regola applicata dal server
  // (`FantasyLineupService._validation_roles`).
  const fieldedRoleById = new Map<string, LineupRole>(
    [...(context?.lineup?.starters ?? []), ...(context?.lineup?.bench ?? [])].map((player) => [
      player.athleteId,
      player.role,
    ]),
  );
  const lockedSet = new Set(lockedAthleteIds);
  const validationRole = (athleteId: string): LineupRole | null =>
    (lockedSet.has(athleteId) ? fieldedRoleById.get(athleteId) : undefined) ??
    playerRole(roster, athleteId);

  const clientEvaluation = evaluateLineup({
    module: moduleCode,
    starters: displayStarters.filter(Boolean).map((athleteId) => ({
      athleteId,
      role: validationRole(athleteId),
    })),
    bench: displayBench.map((athleteId) => ({
      athleteId,
      role: validationRole(athleteId),
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
  // salvataggio non ancora avvenuto.
  const movesRemaining = context?.tacticalMovesRemaining ?? maxMoves - movesUsed;

  // Modifiche non ancora salvate: confronto con lo stato caricato dal server
  // (bozza se c'è, altrimenti formazione confermata).
  const savedState = savedEditorState(context);
  const hasUnsavedChanges =
    lineupSignature({
      module: moduleCode,
      starterIds: displayStarters,
      benchIds: displayBench,
    }) !==
    lineupSignature({
      module: savedState.module,
      starterIds: savedState.starterIds,
      benchIds: savedState.benchIds,
    });

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
      setTurns(list);
      // Stesso turno di default di Turni (EP07-05): il primo non ancora
      // concluso, non un filtro proprio della pagina Formazione — altrimenti
      // le due pagine possono aprirsi su giornate diverse.
      const preferred = resolveDefaultEuropeanTurn(list);
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

  /** Stato "come salvato sul server": bozza se c'è, altrimenti formazione confermata. */
  function savedEditorState(detail: LineupContext | null): {
    module: FantasyModule;
    starterIds: string[];
    benchIds: string[];
  } {
    const draft = detail?.draft;
    if (draft) {
      const templateSlots = starterTemplate(draft.module);
      const starters = [...draft.starterAthleteIds];
      while (starters.length < templateSlots.length) {
        starters.push("");
      }
      return {
        module: draft.module,
        starterIds: starters.slice(0, templateSlots.length),
        benchIds: draft.benchAthleteIds,
      };
    }
    if (detail?.lineup) {
      return {
        module: detail.lineup.module,
        starterIds: detail.lineup.starters.map((player) => player.athleteId),
        benchIds: detail.lineup.bench.map((player) => player.athleteId),
      };
    }
    return {
      module: "4-3-3",
      starterIds: starterTemplate("4-3-3").map(() => ""),
      benchIds: [],
    };
  }

  function applyContext(detail: LineupContext) {
    const saved = savedEditorState(detail);
    setModuleCode(saved.module);
    setStarterIds(saved.starterIds);
    setBenchIds(saved.benchIds);
  }

  async function selectRound(roundId: string) {
    setSelectedRoundId(roundId);
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
      pushToast({
        title: getApiErrorMessage(error, "Formazione del turno non disponibile."),
        variant: "danger",
      });
    } finally {
      setBusy(false);
    }
  }

  function changeModule(next: FantasyModule) {
    const now = context?.serverNow ? new Date(context.serverNow) : new Date();
    // Solo la bozza corrente come fonte, mai concatenata con
    // `context.lineup.starters` — stesso motivo del calcolo di `reservedIds`.
    const lockedIds = starterIds.filter((id) => id && playerLocked(roster, id, now, lockMarginMinutes));
    const preserved = preserveLockedStarters({
      template: starterTemplate(next),
      currentStarters: [...lockedIds, ...starterIds],
      roster,
      now,
    });
    if (lockedIds.some((id) => id && !preserved.includes(id))) {
      pushToast({ title: KICKOFF_LOCK_MESSAGE, variant: "danger" });
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
  }

  function assignStarter(index: number, athleteId: string) {
    const currentId = displayStarters[index] ?? "";
    // Chi occupa lo slot ha già la partita iniziata: non si tocca più.
    if (currentId && currentId !== athleteId && playerLocked(roster, currentId, clock, lockMarginMinutes)) {
      pushToast({ title: KICKOFF_LOCK_MESSAGE, variant: "danger" });
      return;
    }
    // …e non si può far entrare ora chi è già sceso in campo altrove.
    if (playerLocked(roster, athleteId, clock, lockMarginMinutes) && athleteId !== currentId) {
      pushToast({ title: KICKOFF_LOCK_MESSAGE, variant: "danger" });
      return;
    }
    const nextStarters = [...starterIds];
    nextStarters[index] = athleteId;
    setStarterIds(nextStarters);
    setBenchIds(
      orderedBenchFromRoster(
        roster.map((row) => row.athleteId),
        nextStarters,
        benchIds,
      ),
    );
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
      pushToast({ title: orderIssues[0]?.message ?? KICKOFF_LOCK_MESSAGE, variant: "danger" });
      return;
    }
    setBenchIds(next);
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
    // Mosse esaurite e formazione non valida disabilitano già il bottone
    // "Salva formazione" (vedi tacticalEvaluation.issues/clientEvaluation.valid
    // più sotto) — nessun bisogno di intercettarli di nuovo qui.
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
      pushToast({ title: lockIssues[0]?.message ?? KICKOFF_LOCK_MESSAGE, variant: "danger" });
      return;
    }
    if (isDemoMode) {
      if (!DEMO_CONTEXT.modificationAllowed) {
        pushToast({
          title: "Modifica fuori tempo: il cutoff del turno è già trascorso.",
          variant: "danger",
        });
        return;
      }
      pushToast({
        title: tacticalEvaluation.wouldConsume
          ? `Formazione salvata (demo). Mossa tattica ${movesUsed + 1}/${maxMoves} registrata.`
          : "Formazione salvata (demo).",
        variant: "success",
      });
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
      pushToast({ title: "Formazione salvata.", variant: "success" });
    } catch (error) {
      pushToast({
        title: getApiErrorMessage(error, "Salvataggio formazione non riuscito."),
        variant: "danger",
      });
    } finally {
      setBusy(false);
    }
  }

  async function copyFromPrevious() {
    if (isDemoMode) {
      if (!DEMO_CONTEXT.modificationAllowed) {
        pushToast({
          title: "Modifica fuori tempo: il cutoff del turno è già trascorso.",
          variant: "danger",
        });
        return;
      }
      const previous = DEMO_CONTEXT.previousLineup;
      if (!previous) {
        pushToast({ title: "Non c'è una formazione precedente da copiare.", variant: "danger" });
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
        pushToast({ title: copied.issues[0]?.message ?? KICKOFF_LOCK_MESSAGE, variant: "danger" });
        return;
      }
      setModuleCode(copied.module as FantasyModule);
      setStarterIds(copied.starterIds);
      setBenchIds(copied.benchIds);
      pushToast({
        title:
          copied.issues.length > 0
            ? "Formazione precedente copiata in bozza (demo), rivalidata sulla rosa corrente."
            : "Formazione precedente copiata in bozza (demo).",
        variant: "success",
      });
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
      pushToast({
        title:
          detail.copyIssues && detail.copyIssues.length > 0
            ? "Formazione precedente copiata in bozza e rivalidata sulla rosa corrente."
            : "Formazione precedente copiata in bozza.",
        variant: "success",
      });
    } catch (error) {
      pushToast({
        title: getApiErrorMessage(error, "Copia della formazione precedente non riuscita."),
        variant: "danger",
      });
    } finally {
      setBusy(false);
    }
  }

  function revertChanges() {
    if (!context) {
      return;
    }
    applyContext(context);
    pushToast({ title: "Modifiche annullate.", variant: "info" });
  }

  async function applyBestFormation() {
    if (isDemoMode) {
      pushToast({
        title: "Applica formazione migliore non è disponibile in modalità demo.",
        variant: "danger",
      });
      return;
    }
    const session = loadStoredSession();
    if (!session?.accessToken || !activeLeagueId || !selectedRoundId) {
      return;
    }
    setBusy(true);
    try {
      const detail = await applyBestLineup(session.accessToken, activeLeagueId, selectedRoundId);
      setContext(detail);
      applyContext(detail);
      pushToast({ title: "Formazione migliore applicata in bozza.", variant: "success" });
    } catch (error) {
      pushToast({
        title: getApiErrorMessage(error, "Applicazione della formazione migliore non riuscita."),
        variant: "danger",
      });
    } finally {
      setBusy(false);
    }
  }

  async function saveDraft() {
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
      pushToast({ title: lockIssues[0]?.message ?? KICKOFF_LOCK_MESSAGE, variant: "danger" });
      return;
    }
    const draftEvaluation = evaluateLineup({
      module: moduleCode,
      starters: displayStarters.map((athleteId) => ({
        athleteId,
        role: athleteId ? validationRole(athleteId) : null,
      })),
      bench: displayBench.map((athleteId) => ({
        athleteId,
        role: validationRole(athleteId),
      })),
      rosterAthleteIds: roster.map((row) => row.athleteId),
      strict: false,
    });
    if (!draftEvaluation.valid) {
      pushToast({ title: draftEvaluation.issues[0]?.message ?? "Bozza non valida.", variant: "danger" });
      return;
    }
    if (isDemoMode) {
      if (!DEMO_CONTEXT.modificationAllowed) {
        pushToast({
          title: "Modifica fuori tempo: il cutoff del turno è già trascorso.",
          variant: "danger",
        });
        return;
      }
      pushToast({
        title: "Bozza salvata (demo). La conferma non consuma mosse tattiche.",
        variant: "success",
      });
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
      pushToast({
        title: "Bozza salvata. Conferma la formazione quando è completa.",
        variant: "success",
      });
    } catch (error) {
      pushToast({
        title: getApiErrorMessage(error, "Salvataggio bozza non riuscito."),
        variant: "danger",
      });
    } finally {
      setBusy(false);
    }
  }

  const pitchPlayers: PitchPlayer[] = template.map((role, index) => {
    const athleteId = displayStarters[index] ?? "";
    return {
      id: `starter-${index}`,
      name: athleteId ? playerName(roster, athleteId) : "Libero",
      role,
      photoUrl: athleteId ? playerPhotoUrl(roster, athleteId) : null,
      scoreLabel: athleteId ? playerScoreLabel(roster, athleteId) : null,
      badges: athleteId ? playerBadges(roster, athleteId) : [],
    };
  });
  const pitchPositions = layoutFromModule(
    template.map((role, index) => ({ role, index })),
    moduleCode,
    (entry) => entry.role,
    (entry) => `starter-${entry.index}`,
    (entry) => entry.index,
  );
  const maxSubs = context?.maxAutomaticSubstitutions ?? MAX_AUTOMATIC_SUBSTITUTIONS;
  const panchinaIds = displayBench.slice(0, maxSubs);
  const tribunaIds = displayBench.slice(maxSubs);

  const optionsForSlot = (index: number, role: LineupRole) => {
    const currentId = displayStarters[index] ?? "";
    const selected = new Set(
      displayStarters.filter((id, currentIndex) => currentIndex !== index && id),
    );
    return roster
      .filter((row) => {
        // Chi occupa lo slot compare sempre, anche se il suo ruolo non
        // corrisponde a quello dello slot: altrimenti la casella mostra
        // "Seleziona calciatore" pur avendo un calciatore in campo e non si
        // capisce chi stia rendendo il modulo non valido.
        if (row.athleteId === currentId) {
          return true;
        }
        if (row.role !== role || selected.has(row.athleteId)) {
          return false;
        }
        return true;
      })
      .map((row) => {
        const notes = [
          row.role && row.role !== role ? `ruolo ${row.role}, non compatibile` : null,
          playerLocked(roster, row.athleteId, clock, lockMarginMinutes) ? "bloccato" : null,
        ].filter(Boolean);
        return {
          value: row.athleteId,
          label: notes.length > 0 ? `${row.athleteName} (${notes.join(", ")})` : row.athleteName,
        };
      });
  };

  return (
    <PageContainer
      title="Formazione"
      className="fa-formation-page"
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
        <div data-testid="wireframe-formation-success" className="fa-formation-layout">
          <aside className="fa-formation-layout__sidebar">
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
              {context.lineup?.systemGeneratedAi ? (
                <p data-testid="formation-ai-badge">
                  <Badge variant="accent">Gestita automaticamente</Badge>{" "}
                  Formazione scelta dall&apos;automazione IA
                  {context.lineup.aiDecidedAt
                    ? ` il ${formatDateTime(context.lineup.aiDecidedAt)}`
                    : ""}
                  {context.lineup.aiAlgorithmVersion
                    ? ` · ${context.lineup.aiAlgorithmVersion}`
                    : ""}
                  .
                </p>
              ) : null}
              {context.lineup?.autoResolutionSource ? (
                <p data-testid="formation-auto-resolution-badge">
                  <Badge variant="warning">Formazione applicata automaticamente</Badge>{" "}
                  {AUTO_RESOLUTION_MESSAGE[context.lineup.autoResolutionSource]}
                </p>
              ) : null}
              <p data-testid="formation-cutoff">
                Cutoff (primo kickoff): {formatDateTime(context.cutoffAt)} — lock progressivo per
                calciatore
              </p>
              <p data-testid="formation-lock-hint">
                {context.modificationAllowed
                  ? "I calciatori la cui partita è già iniziata restano bloccati anche se l'orario viene rinviato; gli altri restano modificabili."
                  : "Nessun calciatore è più modificabile."}
              </p>
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
                <div data-testid="formation-copy-issues">
                  <p className="fa-formation-layout__issues-title">
                    Se copi la formazione precedente:
                  </p>
                  <ul>
                    {context.copyIssues?.map((issue) => (
                      <li key={`${issue.code}-${issue.message}`}>{issue.message}</li>
                    ))}
                  </ul>
                </div>
              ) : null}
            </CardBody>
          </Card>

          {clientEvaluation.issues.length > 0 ? (
            <div data-testid="formation-issues" className="fa-formation-layout__issues" role="alert">
              <p className="fa-formation-layout__issues-title">
                Da correggere prima di salvare:
              </p>
              <ul>
                {clientEvaluation.issues.map((issue) => (
                  <li key={`${issue.code}-${issue.message}`}>{issue.message}</li>
                ))}
              </ul>
            </div>
          ) : null}

          {tacticalEvaluation.wouldConsume ? (
            <p data-testid="formation-moves-hint" className="fa-formation-layout__moves-hint">
              Questo salvataggio consumerà 1 mossa tattica ({movesRemaining} di {maxMoves}{" "}
              disponibili). Le sostituzioni automatiche non consumano mosse.
            </p>
          ) : null}

          <div className="fa-formation-layout__actions">
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
              onClick={() => void applyBestFormation()}
              data-testid="formation-apply-best"
            >
              Applica formazione migliore
            </Button>
            <Button
              type="button"
              variant="ghost"
              disabled={busy || !canEdit || !hasUnsavedChanges}
              onClick={() => revertChanges()}
              data-testid="formation-revert"
            >
              Annulla modifiche
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
                tacticalEvaluation.issues.length > 0 ||
                !clientEvaluation.valid
              }
              onClick={() => void save()}
              data-testid="formation-save"
            >
              Salva formazione
            </Button>
          </div>
          </aside>

          <div className="fa-formation-layout__main">
          <div className="fa-formation-layout__module-row">
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
            <Badge
              variant={movesRemaining === 0 ? "danger" : movesRemaining === 1 ? "warning" : "neutral"}
              data-testid="formation-moves-badge"
              title={`Mosse tattiche: ${movesUsed}/${maxMoves} usate`}
            >
              Mosse {movesRemaining}/{maxMoves}
            </Badge>
          </div>

          <div className="fa-formation-layout__pitch-row">
          <div className="fa-formation-layout__pitch">
            <FootballPitch
              title={`Modulo ${moduleCode}`}
              pitchAriaLabel="Formazione titolare"
              players={pitchPlayers}
              positions={pitchPositions}
            />
          </div>

          <div
            data-testid="formation-starters"
            className="fa-ds-showcase__stack fa-formation-layout__editor"
          >
            <h3 className="fa-formation-layout__section-title">Modifica titolari</h3>
            {template.map((role, index) => {
              const currentId = displayStarters[index] ?? "";
              const lockedSlot = playerLocked(roster, currentId, clock, lockMarginMinutes);
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
                  onSelect={(athleteId) => assignStarter(index, athleteId)}
                />
              );
            })}
          </div>
          </div>

          <div data-testid="formation-bench-order" className="fa-ds-showcase__stack">
            <p data-testid="formation-sub-hint">
              Entrano al massimo {maxSubs} panchinari, nell&apos;ordine di ingresso sotto e solo a
              parità di ruolo (P con P, D con D, C con C, A con A). Dal {maxSubs + 1}° in poi restano
              fuori se i {maxSubs} cambi sono già stati usati.
            </p>
            {displayBench.length === 0 ? (
              <p data-testid="formation-bench-empty">Nessun panchinaro: tutti i calciatori sono titolari.</p>
            ) : (
              <div className="fa-formation-layout__benches">
                <div>
                  <h4 className="fa-formation-layout__section-title">
                    Panchina — massimo {maxSubs} subentri
                  </h4>
                  {panchinaIds.length === 0 ? (
                    <p data-testid="formation-panchina-empty">Nessun panchinaro disponibile.</p>
                  ) : (
                    <ol className="fa-bench-order" data-testid="formation-bench-panchina">
                      {displayBench.map((athleteId, index) =>
                        index < maxSubs ? (
                          <BenchOrderRow
                            key={athleteId}
                            athleteId={athleteId}
                            index={index}
                            canEnter
                            maxSubs={maxSubs}
                            name={playerName(roster, athleteId)}
                            role={playerRole(roster, athleteId)}
                            locked={playerLocked(roster, athleteId, clock, lockMarginMinutes)}
                            disabled={!context.modificationAllowed || !canEdit}
                            options={displayBench.map((_, target) => ({
                              value: String(target),
                              label: `${target + 1}°`,
                              disabled: !canMoveBenchTo(index, target),
                            }))}
                            onMove={(target) => moveBenchTo(index, target)}
                            scoreLabel={playerScoreLabel(roster, athleteId)}
                          />
                        ) : null,
                      )}
                    </ol>
                  )}
                </div>
                <div>
                  <h4 className="fa-formation-layout__section-title">Tribuna</h4>
                  {tribunaIds.length === 0 ? (
                    <p data-testid="formation-tribuna-empty">
                      Nessuno oltre i {maxSubs} cambi: tutta la rosa disponibile è titolare o in
                      panchina.
                    </p>
                  ) : (
                    <ol className="fa-bench-order" data-testid="formation-bench-tribuna">
                      {displayBench.map((athleteId, index) =>
                        index >= maxSubs ? (
                          <BenchOrderRow
                            key={athleteId}
                            athleteId={athleteId}
                            index={index}
                            canEnter={false}
                            maxSubs={maxSubs}
                            name={playerName(roster, athleteId)}
                            role={playerRole(roster, athleteId)}
                            locked={playerLocked(roster, athleteId, clock, lockMarginMinutes)}
                            disabled={!context.modificationAllowed || !canEdit}
                            options={displayBench.map((_, target) => ({
                              value: String(target),
                              label: `${target + 1}°`,
                              disabled: !canMoveBenchTo(index, target),
                            }))}
                            onMove={(target) => moveBenchTo(index, target)}
                            scoreLabel={playerScoreLabel(roster, athleteId)}
                          />
                        ) : null,
                      )}
                    </ol>
                  )}
                </div>
              </div>
            )}
          </div>
          </div>
        </div>
      ) : null}
    </PageContainer>
  );
}
