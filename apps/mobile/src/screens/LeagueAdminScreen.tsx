import { lazyStyles } from "../theme/lazyStyles";
import type {
  CalendarActionModalState,
  CalendarRosterTeamIssues,
  CreatedLeagueInvite,
  LeagueCalendar,
  LeagueInvite,
  LeagueLifecycle,
  FantasyCoachDirectoryItem,
  LeagueMember,
  LeagueRules,
  RemovalCounts,
  UpdateLeagueRulesRequest,
} from "@fantappero/contracts";
import {
  CALENDAR_CONFIRMED_MESSAGE,
  CALENDAR_PANEL_INTRO,
  avatarInitials,
  calendarErrorNeedsParticipants,
  calendarGeneratedMessage,
  memberRemovedMessage,
  missingMembersLabel,
  orderLeagueSetupBlockers,
  removeMemberConfirmation,
} from "@fantappero/contracts";
import { theme } from "@fantappero/ui/theme";
import { useNavigation, useRoute, type RouteProp } from "@react-navigation/core";
import type { NativeStackNavigationProp } from "@react-navigation/native-stack";
import { useCallback, useEffect, useRef, useState } from "react";
import type { ReactNode } from "react";
import {
  Modal,
  Pressable,
  ScrollView,
  type ScrollViewInstance,
  StyleSheet,
  Switch,
  Text,
  View,
} from "react-native";
import { AppTextInput as TextInput } from "../components/AppTextInput";
import { ApiError } from "../api/client";
import {
  assignRandomAiRoster,
  calendarRosterIssuesFromError,
  confirmLeagueCalendar,
  createLeagueInvite,
  deleteLeague,
  ensureFantasyTeams,
  ensureFantasyTurns,
  fetchLeagueAdminPanel,
  fetchLeagueCalendarAdmin,
  fetchLeagueCalendarRosterCheck,
  fetchLeagueInvites,
  fetchLeagueMembers,
  generateLeagueCalendar,
  removeLeagueMember,
  replaceLeagueMember,
  revokeLeagueAdmin,
  revokeLeagueInvite,
  transferLeagueAdmin,
  updateLeagueRules,
} from "../api/leagues";
import { fetchManagerDirectory } from "../api/managerInvites";
import { AppTextInput } from "../components/AppTextInput";
import { AvatarWithFallback } from "../components/AvatarWithFallback";
import { CalendarActionDialog } from "../components/CalendarActionDialog";
import { CoachDirectoryPanel } from "../components/CoachDirectoryPanel";
import { ConfirmDialog } from "../components/ConfirmDialog";
import { ScreenTabs } from "../components/ScreenTabs";
import { UiStatePanel } from "../components/UiStatePanel";
import { useScreenData } from "../hooks/useScreenData";
import { PageContainer } from "../layout/PageContainer";
import {
  calendarButtonsDisabled,
  calendarModalAfterCheck,
  calendarModalAfterError,
  calendarModalChecking,
  participantsShortcutTab,
} from "../leagues/calendarModalFlow";
import { isLeagueDeletable, stackAfterLeagueDeleted } from "../leagues/leagueDeleteHelpers";
import { leagueStateLabel } from "../leagues/leagueLabels";
import {
  RANDOM_ROSTER_FALLBACK_ERROR,
  RANDOM_ROSTER_ONLY_AI_MESSAGE,
  RANDOM_ROSTER_TEAM_MISSING_MESSAGE,
  canAssignRandomRoster,
  canManageMember,
  canOpenMemberProfile,
  memberRoleLabel,
  randomRosterAssignedMessage,
} from "../leagues/memberRow";
import { rulesSavedMessage } from "../leagues/rulesSaved";
import { MarketGateBarView } from "../market/MarketGateBar";
import { pendingInvitesLabel } from "../market/marketGateNotice";
import { useMarketGate } from "../market/useMarketGate";
import type { RootStackParamList } from "../navigation/types";
import { getApiErrorMessage, useAuthSession } from "../session/DemoSessionContext";
import { resolveAvatarUrl } from "../utils/avatar";
import { copyToClipboard } from "../utils/clipboard";

const { colors, spacing, typography, radius } = theme;


type SetupTab = "configurazione" | "invitati";

function clampPercent(text: string, fallback: number): number {
  if (text.trim() === "" || Number.isNaN(Number(text))) {
    return fallback;
  }
  return Math.min(100, Math.max(0, Number(text)));
}

function buildPayloadFromRules(rules: LeagueRules): UpdateLeagueRulesRequest {
  return {
    presetName: rules.presetName,
    participantCount: rules.participantCount,
    roster: { ...rules.roster },
    totalCredits: rules.totalCredits,
    minFixturesPerRound: rules.minFixturesPerRound,
    turnCoverageThreshold: rules.turnCoverageThreshold,
    lineupLockMarginMinutes: rules.lineupLockMarginMinutes,
    minutesThreshold: rules.minutesThreshold,
    voluntaryReleaseRefundPercent: rules.voluntaryReleaseRefundPercent,
    leagueExitRefundPercent: rules.leagueExitRefundPercent,
    maxActiveTradeProposalsPerTeam: rules.maxActiveTradeProposalsPerTeam,
    options: { ...rules.options },
  };
}

function formatDate(value: string): string {
  return new Intl.DateTimeFormat("it-IT", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

export function LeagueAdminScreen() {
  const navigation = useNavigation<NativeStackNavigationProp<RootStackParamList>>();
  const route = useRoute<RouteProp<RootStackParamList, "LeagueAdmin">>();
  const {
    can,
    accessToken,
    activeLeagueId,
    activeLeague,
    setActiveLeagueId,
    unregisterLeague,
    refreshMemberships,
    user,
  } = useAuthSession();

  const leagueId = route.params?.leagueId ?? activeLeagueId;

  useEffect(() => {
    if (route.params?.leagueId) {
      setActiveLeagueId(route.params.leagueId);
    }
  }, [route.params?.leagueId, setActiveLeagueId]);

  const [rules, setRules] = useState<LeagueRules | null>(null);
  const [lifecycle, setLifecycle] = useState<LeagueLifecycle | null>(null);
  const [members, setMembers] = useState<LeagueMember[]>([]);
  // Sostituzione fantallenatore: finestra a due passi (chi togliere, chi mettere).
  const [replaceOpen, setReplaceOpen] = useState(false);
  const [replaceFromId, setReplaceFromId] = useState("");
  const [replaceToId, setReplaceToId] = useState("");
  const [replaceQuery, setReplaceQuery] = useState("");
  const [replaceError, setReplaceError] = useState<string | null>(null);
  const [candidates, setCandidates] = useState<FantasyCoachDirectoryItem[]>([]);
  const [candidatesLoading, setCandidatesLoading] = useState(false);
  const [invites, setInvites] = useState<LeagueInvite[]>([]);
  const [createdInvite, setCreatedInvite] = useState<CreatedLeagueInvite | null>(null);
  const [calendar, setCalendar] = useState<LeagueCalendar | null>(null);
  // «Genera/Conferma calendario» apre la finestra con il controllo delle rose (1.5).
  const [calendarModal, setCalendarModal] = useState<CalendarActionModalState | null>(null);
  const [calendarError, setCalendarError] = useState<string | null>(null);
  const [calendarSuccess, setCalendarSuccess] = useState<string | null>(null);
  // «Rimuovi» chiede prima «Sei sicuro?» con il nome (1.5).
  const [removeTarget, setRemoveTarget] = useState<LeagueMember | null>(null);
  const [membersSuccess, setMembersSuccess] = useState<string | null>(null);
  const [expiresInDays, setExpiresInDays] = useState(7);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [saveSuccess, setSaveSuccess] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [workingId, setWorkingId] = useState<string | null>(null);
  const [copyFeedback, setCopyFeedback] = useState<string | null>(null);
  const [copyError, setCopyError] = useState<string | null>(null);
  const [deleteConfirmed, setDeleteConfirmed] = useState(false);
  const [deleteSuccess, setDeleteSuccess] = useState<string | null>(null);
  const [participantCountText, setParticipantCountText] = useState("8");
  const [minutesThresholdText, setMinutesThresholdText] = useState("15");
  const [lockMarginText, setLockMarginText] = useState("15");
  const [configurationSaved, setConfigurationSaved] = useState(false);
  const [setupTab, setSetupTab] = useState<SetupTab>("configurazione");
  // «Vai a Partecipanti» (errore del calendario) porta la pagina fino a «Prossime fasi». Le
  // misure `onLayout` sono relative al blocco che le contiene: si sommano il blocco nel corpo
  // della pagina e il titolo nel blocco. Il titolo della pagina e le schede «Home lega» sopra al
  // corpo non rientrano nella somma: la pagina si ferma un po' più su del titolo «Prossime fasi»,
  // che resta ben visibile sotto il bordo alto.
  const pageScrollRef = useRef<ScrollViewInstance>(null);
  const setupBlockYRef = useRef(0);
  const setupHeadingYRef = useRef(0);
  const [creditsText, setCreditsText] = useState("1000");
  const [turnCoverageText, setTurnCoverageText] = useState("75");
  const [voluntaryRefundText, setVoluntaryRefundText] = useState("50");
  const [exitRefundText, setExitRefundText] = useState("100");
  const [maxTradeProposalsText, setMaxTradeProposalsText] = useState("10");

  const loadAll = useCallback(
    async (options?: { silent?: boolean }) => {
      setActionError(null);
      setSaveSuccess(null);
      if (!leagueId || !accessToken) {
        setLoading(false);
        setRules(null);
        setLoadError(!leagueId ? null : "Sessione non disponibile. Accedi di nuovo.");
        return;
      }

      if (!options?.silent) {
        setLoading(true);
      }
      setLoadError(null);
      try {
        const [panel, memberRows, inviteRows, cal] = await Promise.all([
          fetchLeagueAdminPanel(accessToken, leagueId),
          fetchLeagueMembers(accessToken, leagueId),
          fetchLeagueInvites(accessToken, leagueId),
          fetchLeagueCalendarAdmin(accessToken, leagueId),
        ]);
        setRules(panel.rules);
        setLifecycle(panel.lifecycle);
        setConfigurationSaved(panel.configurationSaved);
        setParticipantCountText(String(panel.rules.participantCount));
        setMinutesThresholdText(String(panel.rules.minutesThreshold));
        setLockMarginText(String(panel.rules.lineupLockMarginMinutes));
        setCreditsText(String(panel.rules.totalCredits));
        setTurnCoverageText(String(Math.round(panel.rules.turnCoverageThreshold * 100)));
        setVoluntaryRefundText(String(panel.rules.voluntaryReleaseRefundPercent));
        setExitRefundText(String(panel.rules.leagueExitRefundPercent));
        setMaxTradeProposalsText(String(panel.rules.maxActiveTradeProposalsPerTeam));
        setMembers(memberRows);
        setInvites(inviteRows);
        setCalendar(cal);
      } catch (error) {
        setLoadError(getApiErrorMessage(error, "Impossibile caricare l'amministrazione."));
        setRules(null);
        setLifecycle(null);
      } finally {
        setLoading(false);
      }
    },
    [accessToken, leagueId],
  );

  const { refreshing, onRefresh } = useScreenData(loadAll);
  // Lo stato del mercato serve all'interruttore e al conto degli iscritti, inviti nominativi in
  // attesa compresi (Rosario, 20/11): si rilegge quando cambiano iscritti, inviti o regolamento
  // («Salva regolamento» può cambiare i partecipanti, QA 24-25/11).
  const [invitesReload, setInvitesReload] = useState(0);
  const [rulesReload, setRulesReload] = useState(0);
  const marketGate = useMarketGate({ reloadToken: members.length + invitesReload + rulesReload });
  const pendingInviteCount = marketGate.pendingInviteCount;

  // Amministratori: passare il controllo, condividerlo (co-admin) o toglierlo a un co-admin.
  const [menuOpen, setMenuOpen] = useState(false);
  const [adminOpen, setAdminOpen] = useState(false);
  const [adminTargetId, setAdminTargetId] = useState("");
  const [adminMode, setAdminMode] = useState<"co_admin" | "transfer">("co_admin");
  const [adminError, setAdminError] = useState<string | null>(null);

  useEffect(() => {
    if (!replaceOpen || !leagueId || !accessToken) {
      return;
    }
    const timer = setTimeout(() => {
      setCandidatesLoading(true);
      void fetchManagerDirectory(accessToken, leagueId, {
        query: replaceQuery.trim() || undefined,
        available: true,
        pageSize: 8,
      })
        .then((result) =>
          setCandidates(result.items.filter((item) => !item.inLeague && !item.isSelf)),
        )
        .catch(() => setCandidates([]))
        .finally(() => setCandidatesLoading(false));
    }, 250);
    return () => clearTimeout(timer);
  }, [replaceOpen, replaceQuery, leagueId, accessToken]);

  // Tutti gli hook stanno sopra questo return: dopo «Elimina lega» la lega sparisce dalla
  // sessione, il permesso cade e la schermata si ridisegna da qui. Con hook più in basso
  // React vedeva meno hook del giro prima e mostrava «Qualcosa è andato storto» (QA 22→23/11).
  if (!can(["league:admin"])) {
    return (
      <PageContainer title="Amministrazione lega" testID="screen-league-admin">
        <UiStatePanel
          state="forbidden"
          title="Permessi insufficienti"
          message="Solo l'amministratore della lega può gestire partecipanti e inviti."
          testID="league-admin-forbidden"
        />
      </PageContainer>
    );
  }

  async function onSaveRules() {
    if (!rules) {
      return;
    }
    setActionError(null);
    setSaveSuccess(null);
    const nextRules: LeagueRules = {
      ...rules,
      participantCount: Number(participantCountText) || rules.participantCount,
      minutesThreshold: Number(minutesThresholdText) || rules.minutesThreshold,
      lineupLockMarginMinutes: Number(lockMarginText) || rules.lineupLockMarginMinutes,
      totalCredits: Number(creditsText) || rules.totalCredits,
      turnCoverageThreshold:
        Math.min(100, Math.max(50, Number(turnCoverageText) || 0)) / 100 ||
        rules.turnCoverageThreshold,
      voluntaryReleaseRefundPercent: clampPercent(
        voluntaryRefundText,
        rules.voluntaryReleaseRefundPercent,
      ),
      leagueExitRefundPercent: clampPercent(exitRefundText, rules.leagueExitRefundPercent),
      maxActiveTradeProposalsPerTeam:
        Math.max(1, Number(maxTradeProposalsText) || 0) || rules.maxActiveTradeProposalsPerTeam,
    };
    if (!leagueId || !accessToken) {
      setActionError("Seleziona una lega e accedi di nuovo.");
      return;
    }
    setWorkingId("rules");
    try {
      const saved = await updateLeagueRules(
        accessToken,
        leagueId,
        buildPayloadFromRules(nextRules),
      );
      setRules(saved);
      setRulesReload((current) => current + 1);
      // Si resta sul regolamento con la conferma, senza passare a «Invitati» (corsa M4, 22/11).
      setSaveSuccess(rulesSavedMessage(!configurationSaved));
      setConfigurationSaved(true);
    } catch (error) {
      setActionError(getApiErrorMessage(error, "Impossibile salvare il regolamento."));
    } finally {
      setWorkingId(null);
    }
  }

  async function onCreateInvite() {
    setActionError(null);
    setCopyFeedback(null);
    setCopyError(null);
    if (!leagueId || !accessToken) {
      setActionError("Sessione non disponibile. Accedi di nuovo.");
      return;
    }
    setWorkingId("create-invite");
    try {
      const created = await createLeagueInvite(accessToken, leagueId, { expiresInDays });
      setCreatedInvite(created);
      setInvites((current) => [created, ...current]);
    } catch (error) {
      setActionError(getApiErrorMessage(error, "Impossibile generare l'invito."));
    } finally {
      setWorkingId(null);
    }
  }

  async function onCopy(value: string, label: string) {
    setCopyFeedback(null);
    setCopyError(null);
    try {
      await copyToClipboard(value);
      setCopyFeedback(`${label} copiato negli appunti.`);
    } catch {
      setCopyError(`Impossibile copiare ${label.toLowerCase()}. Condividi manualmente.`);
    }
  }

  async function onRevoke(inviteId: string) {
    setActionError(null);
    if (!leagueId || !accessToken) {
      setActionError("Sessione non disponibile. Accedi di nuovo.");
      return;
    }
    setWorkingId(inviteId);
    try {
      const revoked = await revokeLeagueInvite(accessToken, leagueId, inviteId);
      setInvites((current) =>
        current.map((invite) => (invite.id === revoked.id ? revoked : invite)),
      );
    } catch (error) {
      setActionError(getApiErrorMessage(error, "Impossibile revocare l'invito."));
    } finally {
      setWorkingId(null);
    }
  }

  function openAdmin() {
    setAdminTargetId("");
    setAdminMode("co_admin");
    setAdminError(null);
    setAdminOpen(true);
  }

  async function onAdminChange(action: () => Promise<void>) {
    setAdminError(null);
    setWorkingId("admin");
    try {
      await action();
      setAdminOpen(false);
      await loadAll({ silent: true });
    } catch (error) {
      setAdminError(getApiErrorMessage(error, "Impossibile modificare gli amministratori."));
    } finally {
      setWorkingId(null);
    }
  }

  async function onConfirmAdmin() {
    if (!adminTargetId || !leagueId || !accessToken) {
      return;
    }
    const keepCurrent = adminMode === "co_admin";
    await onAdminChange(async () => {
      await transferLeagueAdmin(accessToken, leagueId, adminTargetId, keepCurrent);
    });
  }

  async function onRevokeAdmin(userId: string) {
    if (!leagueId || !accessToken) {
      return;
    }
    await onAdminChange(async () => {
      await revokeLeagueAdmin(accessToken, leagueId, userId);
    });
  }

  function openReplace() {
    setReplaceFromId("");
    setReplaceToId("");
    setReplaceQuery("");
    setReplaceError(null);
    setCandidates([]);
    setReplaceOpen(true);
  }

  async function onReplace() {
    if (!replaceFromId || !replaceToId || !leagueId || !accessToken) {
      return;
    }
    setReplaceError(null);
    setWorkingId("replace");
    try {
      await replaceLeagueMember(accessToken, leagueId, replaceFromId, replaceToId);
      setReplaceOpen(false);
      await loadAll({ silent: true });
    } catch (error) {
      setReplaceError(getApiErrorMessage(error, "Impossibile sostituire il fantallenatore."));
    } finally {
      setWorkingId(null);
    }
  }

  /**
   * Previsti, minimo e iscritti rimasti dopo «Rimuovi», letti prima della rimozione: servono a
   * dire se i previsti cambiano davvero (stessa regola del server).
   */
  function removalCounts(): RemovalCounts {
    return {
      participantCount: rules?.participantCount,
      participantMin: rules?.participantMin,
      remaining: Math.max(0, members.length - 1),
    };
  }

  async function onRemove(userId: string, displayName: string) {
    setActionError(null);
    setMembersSuccess(null);
    if (!leagueId || !accessToken) {
      return;
    }
    const counts = removalCounts();
    setWorkingId(`remove-${userId}`);
    try {
      await removeLeagueMember(accessToken, leagueId, userId);
      // Il backend abbassa participantCount agli iscritti rimasti (se ne restano almeno 4 e i
      // previsti sono di più): ricarica tutto.
      await loadAll();
      setMembersSuccess(memberRemovedMessage(displayName, counts));
    } catch (error) {
      setActionError(getApiErrorMessage(error, `Impossibile rimuovere ${displayName}.`));
    } finally {
      setWorkingId(null);
    }
  }

  /** «Assegna rosa random» per un fantallenatore IA (come sul sito). */
  async function onAssignRandomRoster(target: LeagueMember) {
    setActionError(null);
    setMembersSuccess(null);
    if (target.userType !== "ai") {
      setActionError(RANDOM_ROSTER_ONLY_AI_MESSAGE);
      return;
    }
    if (!leagueId || !accessToken) {
      setActionError("Sessione non disponibile. Accedi di nuovo.");
      return;
    }
    setWorkingId(`random-${target.userId}`);
    try {
      const ensured = await ensureFantasyTeams(accessToken, leagueId);
      const team = ensured.teams.find((row) => row.userId === target.userId);
      if (!team) {
        setActionError(RANDOM_ROSTER_TEAM_MISSING_MESSAGE);
        return;
      }
      const updated = await assignRandomAiRoster(accessToken, leagueId, team.id);
      setMembersSuccess(randomRosterAssignedMessage(target.displayName, updated));
    } catch (error) {
      setActionError(getApiErrorMessage(error, RANDOM_ROSTER_FALLBACK_ERROR));
    } finally {
      setWorkingId(null);
    }
  }

  /**
   * «Genera/Conferma calendario» apre la finestra: prima si verificano le rose, poi la conferma
   * «Vuoi generare il calendario?» o l'avviso con «Genera/Conferma comunque» (come sul sito).
   */
  async function openCalendarModal(action: "generate" | "confirm") {
    setCalendarError(null);
    setCalendarSuccess(null);
    setCalendarModal(calendarModalChecking(action));
    if (!leagueId || !accessToken) {
      setCalendarModal(calendarModalAfterCheck(calendarModalChecking(action), action, []));
      return;
    }
    let teams: CalendarRosterTeamIssues[] = [];
    try {
      teams = (await fetchLeagueCalendarRosterCheck(accessToken, leagueId)).teams;
    } catch {
      // Verifica non riuscita: conferma normale; se le rose non sono in regola lo dice l'azione
      // stessa (`league_rosters_invalid`) e la finestra passa all'avviso.
    }
    setCalendarModal((current) => calendarModalAfterCheck(current, action, teams));
  }

  function closeCalendarModal() {
    if (workingId === null) {
      setCalendarModal(null);
    }
  }

  async function runCalendarAction(action: "generate" | "confirm", force: boolean) {
    setCalendarError(null);
    setCalendarSuccess(null);
    if (!leagueId || !accessToken) {
      setCalendarModal(null);
      setCalendarError("Sessione non disponibile. Accedi di nuovo.");
      return;
    }
    setWorkingId(action === "generate" ? "calendar-generate" : "calendar-confirm");
    try {
      if (action === "generate") {
        let next: LeagueCalendar;
        try {
          next = await generateLeagueCalendar(accessToken, leagueId, { force });
        } catch (error) {
          // I Turni Europei di questa lega non esistono ancora (lega nuova, mai
          // entrata nella finestra del cron automatico che copre solo le leghe
          // già attive): li sincronizziamo al volo e riproviamo, così "Genera
          // calendario" resta un solo bottone per l'intera catena.
          if (!(error instanceof ApiError) || error.code !== "european_turns_missing") {
            throw error;
          }
          await ensureFantasyTurns(accessToken, leagueId);
          next = await generateLeagueCalendar(accessToken, leagueId, { force });
        }
        setCalendarModal(null);
        setCalendar(next);
        setCalendarSuccess(calendarGeneratedMessage(next));
      } else {
        const next = await confirmLeagueCalendar(accessToken, leagueId, { force });
        setCalendarModal(null);
        setCalendar(next);
        setCalendarSuccess(CALENDAR_CONFIRMED_MESSAGE);
        try {
          const panel = await fetchLeagueAdminPanel(accessToken, leagueId);
          setLifecycle(panel.lifecycle);
        } catch {
          // Calendario già confermato; il lifecycle si aggiorna al prossimo refresh.
        }
      }
    } catch (error) {
      // Rose non in regola: la finestra passa all'avviso; ogni altro errore resta nel pannello.
      const next = calendarModalAfterError(action, calendarRosterIssuesFromError(error));
      setCalendarModal(next);
      if (!next) {
        setCalendarError(
          getApiErrorMessage(
            error,
            action === "generate"
              ? "Impossibile generare il calendario."
              : "Impossibile confermare il calendario.",
          ),
        );
      }
    } finally {
      setWorkingId(null);
    }
  }

  async function onDelete() {
    setActionError(null);
    setDeleteSuccess(null);
    if (!deleteConfirmed) {
      setActionError("Conferma esplicitamente l'eliminazione spuntando la casella.");
      return;
    }
    if (!leagueId || !accessToken) {
      setActionError("Sessione non disponibile. Accedi di nuovo.");
      return;
    }
    setWorkingId("delete");
    try {
      await deleteLeague(accessToken, leagueId);
      unregisterLeague(leagueId);
      try {
        await refreshMemberships();
      } catch {
        // Eliminazione già riuscita.
      }
      setDeleteSuccess("Lega eliminata definitivamente.");
      // Pila nuova: «indietro» non torna sull'Amministrazione della lega eliminata (QA 23/11).
      navigation.reset(stackAfterLeagueDeleted());
    } catch (error) {
      setActionError(getApiErrorMessage(error, "Impossibile eliminare la lega."));
    } finally {
      setWorkingId(null);
    }
  }

  const calendarLocked = calendarButtonsDisabled({
    working: workingId === "calendar-generate" || workingId === "calendar-confirm",
    modalOpen: calendarModal !== null,
  });
  const canConfigure =
    lifecycle?.state === "draft" || lifecycle?.state === "configuring";
  const leagueName = activeLeague?.name ?? "Lega";
  const currentState = lifecycle?.state ?? "draft";

  return (
    <PageContainer
      title="Amministrazione lega"
      testID="screen-league-admin"
      scrollRef={pageScrollRef}
      refreshing={refreshing}
      onRefresh={onRefresh}
    >
      <ScreenTabs
        items={[
          { id: "league-home", label: "Home lega" },
          { id: "league-admin", label: "Amministrazione lega" },
        ]}
        activeId="league-admin"
        onSelect={(id) => {
          if (id === "league-home" && leagueId) {
            navigation.replace("LeagueHome", { leagueId });
          }
        }}
        testID="league-hub-tabs"
      />
      {loading ? (
        <UiStatePanel
          state="loading"
          title="Caricamento configurazione"
          message="Recupero regolamento e opzioni in corso…"
          testID="league-admin-loading"
        />
      ) : null}

      {!loading && loadError ? (
        <UiStatePanel
          state="error"
          title="Errore di caricamento"
          message={loadError}
          testID="league-admin-error"
        />
      ) : null}

      {!loading && !loadError && !rules ? (
        <UiStatePanel
          state="empty"
          title="Nessuna lega selezionata"
          message="Seleziona una lega e imposta il regolamento prima dell'avvio."
          testID="league-admin-empty"
        />
      ) : null}

      {actionError ? (
        <UiStatePanel
          state="error"
          title="Operazione non riuscita"
          message={actionError}
          testID="league-admin-action-error"
        />
      ) : null}

      {!loading && rules && lifecycle ? (
        <View
          style={styles.content}
          onLayout={(event) => {
            setupBlockYRef.current = event.nativeEvent.layout.y;
          }}
        >
          {calendar?.status === "confirmed" ? null : (
            <>
              <Text style={styles.heading}>Calendario fantallenatori</Text>
              <View style={styles.section} testID="league-calendar-panel">
                <Text style={styles.body} testID="league-calendar-status">
                  Stato: {calendar ? "Anteprima" : "Non generato"}
                  {calendar
                    ? ` · ${calendar.matchupCount} incontri · ${calendar.roundCount} giornate${
                        calendar.byeCount > 0 ? ` · ${calendar.byeCount} riposi` : ""
                      }`
                    : ""}
                </Text>
                <Text style={styles.body}>
                  {CALENDAR_PANEL_INTRO} Gli scontri si consultano nel tab Turni, giornata per
                  giornata.
                </Text>

                {!calendar ? (
                  <Text style={styles.body} testID="league-calendar-empty">
                    Completa le rose di tutti i partecipanti, poi genera il calendario.
                  </Text>
                ) : null}

                {calendarError ? (
                  <UiStatePanel
                    state="error"
                    title="Operazione non completata"
                    message={calendarError}
                    testID="league-calendar-action-error"
                  />
                ) : null}
                {calendarErrorNeedsParticipants(calendarError) ? (
                  <Pressable
                    accessibilityRole="button"
                    onPress={() => {
                      // «Invitati» è disattivata a configurazione non salvata: si va dove c'è «Salva».
                      setSetupTab(participantsShortcutTab(configurationSaved));
                      pageScrollRef.current?.scrollTo({
                        y: Math.max(0, setupBlockYRef.current + setupHeadingYRef.current),
                        animated: true,
                      });
                    }}
                    style={styles.secondaryButton}
                    testID="league-calendar-goto-participants"
                  >
                    <Text style={styles.secondaryLabel}>Vai a Partecipanti</Text>
                  </Pressable>
                ) : null}
                {calendarSuccess ? (
                  <UiStatePanel
                    state="success"
                    title="Calendario aggiornato"
                    message={calendarSuccess}
                    testID="league-calendar-success"
                  />
                ) : null}

                <Pressable
                  accessibilityRole="button"
                  disabled={calendarLocked}
                  onPress={() => void openCalendarModal("generate")}
                  style={[styles.primaryButton, calendarLocked && styles.disabled]}
                  testID="league-calendar-generate"
                >
                  <Text style={styles.primaryLabel}>
                    {workingId === "calendar-generate" ? "Generazione…" : "Genera calendario"}
                  </Text>
                </Pressable>
                {calendar ? (
                  <Pressable
                    accessibilityRole="button"
                    disabled={calendarLocked}
                    onPress={() => void openCalendarModal("confirm")}
                    style={[styles.secondaryButton, calendarLocked && styles.disabled]}
                    testID="league-calendar-confirm"
                  >
                    <Text style={styles.secondaryLabel}>
                      {workingId === "calendar-confirm" ? "Conferma…" : "Conferma calendario"}
                    </Text>
                  </Pressable>
                ) : null}
              </View>
            </>
          )}

          <Text style={styles.heading}>Stato stagione</Text>
          <View style={styles.section} testID="league-season-panel">
            <Text style={styles.body}>Stato corrente: {leagueStateLabel(currentState)}</Text>
            {lifecycle.blockers.length > 0 ? (
              <Text style={styles.body}>
                Completa i passaggi in ordine (partecipanti → rose → calendario): la stagione parte
                in automatico quando tutto è pronto.
              </Text>
            ) : null}
            {orderLeagueSetupBlockers(lifecycle.blockers).map((blocker) => (
              <Text key={blocker.code} style={styles.body}>
                ·{" "}
                {blocker.actionable
                  ? blocker.message
                  : `Completa prima il passaggio precedente. (${blocker.message})`}
              </Text>
            ))}
            {currentState === "active" ? (
              <Text style={styles.body} testID="league-season-in-progress">
                La lega si concluderà automaticamente quando tutte le giornate saranno omologate.
              </Text>
            ) : null}
          </View>

          {/* Interruttore «Mercato aperto»: a lega incompleta non si accende (decisione del 20/11). */}
          <View testID="league-admin-market">
            <MarketGateBarView gate={marketGate} />
          </View>

          <Text
            style={styles.heading}
            onLayout={(event) => {
              setupHeadingYRef.current = event.nativeEvent.layout.y;
            }}
          >
            Prossime fasi
          </Text>
          {/* Solo finché la configurazione non è salvata: una lega avviata conta come
              configurata anche senza un salvataggio del regolamento (Rosario 22/11). */}
          {!configurationSaved ? (
            <Text style={styles.body} testID="league-admin-save-first">
              Prima salva la configurazione della lega, poi invita i fantallenatori.
            </Text>
          ) : null}
          <ScreenTabs
            items={[
              { id: "configurazione", label: "Configurazione" },
              { id: "invitati", label: "Invitati" },
            ]}
            activeId={setupTab}
            disabledIds={configurationSaved ? [] : ["invitati"]}
            onSelect={(id) => {
              if (id === "invitati" && !configurationSaved) {
                return;
              }
              setSetupTab(id as SetupTab);
            }}
            testID="league-admin-setup-tabs"
          />
          {setupTab === "configurazione" ? (
            <>
          <Text style={styles.heading}>Regolamento</Text>
          <Text style={styles.label}>Preset regolamento</Text>
          <Text style={styles.body} testID="league-admin-preset">
            Standard
          </Text>
          <Text style={styles.label}>Partecipanti</Text>
          <TextInput
            value={participantCountText}
            onChangeText={setParticipantCountText}
            keyboardType="number-pad"
            editable={canConfigure}
            style={styles.input}
            accessibilityLabel="Partecipanti"
            testID="league-admin-participant-count"
          />
          <Text style={styles.label}>Crediti iniziali</Text>
          <TextInput
            value={creditsText}
            onChangeText={setCreditsText}
            keyboardType="number-pad"
            editable={canConfigure}
            style={styles.input}
            accessibilityLabel="Crediti iniziali"
            testID="league-admin-credits"
          />
          <Text style={styles.label}>Soglia minuti per il voto</Text>
          <TextInput
            value={minutesThresholdText}
            onChangeText={setMinutesThresholdText}
            keyboardType="number-pad"
            editable={canConfigure}
            style={styles.input}
            accessibilityLabel="Soglia minuti per il voto"
            testID="league-admin-minutes-threshold"
          />
          <Text style={styles.label}>Margine di preavviso lock formazione (minuti)</Text>
          <TextInput
            value={lockMarginText}
            onChangeText={setLockMarginText}
            keyboardType="number-pad"
            editable={canConfigure}
            style={styles.input}
            accessibilityLabel="Margine di preavviso lock formazione (minuti)"
            testID="league-admin-lock-margin"
          />
          <Text style={styles.body} testID="league-admin-lock-margin-hint">
            Un giocatore si blocca in formazione questi minuti prima dell&apos;inizio della sua partita reale — non del turno intero: la formazione a step resta invariata.
          </Text>
          <Text style={styles.label}>Titolari minimi schierabili per giocare il turno (%)</Text>
          <TextInput
            value={turnCoverageText}
            onChangeText={setTurnCoverageText}
            keyboardType="number-pad"
            editable={canConfigure}
            style={styles.input}
            accessibilityLabel="Titolari minimi schierabili per giocare il turno (%)"
            testID="league-admin-turn-coverage"
          />
          <Text style={styles.body} testID="league-admin-turn-coverage-hint">
            Percentuale dei titolari che ogni fantallenatore deve poter schierare perché una giornata diventi un Turno Europeo valido e quindi giocabile (minimo 50%, massimo 100%).
          </Text>
          <Text style={styles.label}>Rosa standard (fissa)</Text>
          <Text style={styles.body} testID="league-admin-roster">
            {`${rules.roster.rosterSize} giocatori: ${rules.roster.goalkeepers}P-${rules.roster.defenders}D-${rules.roster.midfielders}C-${rules.roster.forwards}A`}
          </Text>
          <Text style={styles.label}>Opzioni lega</Text>
          <View style={styles.switchRow}>
            <Text style={[styles.body, styles.switchLabel]}>Abilita scambi</Text>
            <Switch
              value={rules.options.allowTrades}
              disabled={!canConfigure}
              onValueChange={(value) =>
                setRules({
                  ...rules,
                  options: { ...rules.options, allowTrades: value },
                })
              }
            />
          </View>
          <View style={styles.switchRow}>
            <Text style={[styles.body, styles.switchLabel]}>Abilita inviti manuali</Text>
            <Switch
              value={rules.options.allowManualInvites}
              disabled={!canConfigure}
              onValueChange={(value) =>
                setRules({
                  ...rules,
                  options: { ...rules.options, allowManualInvites: value },
                })
              }
            />
          </View>
          <View style={styles.switchRow}>
            <Text style={[styles.body, styles.switchLabel]}>Richiedi approvazione amministratore per gli scambi</Text>
            <Switch
              value={rules.options.requireTradeApproval}
              disabled={!canConfigure}
              onValueChange={(value) =>
                setRules({
                  ...rules,
                  options: { ...rules.options, requireTradeApproval: value },
                })
              }
            />
          </View>
          <Text style={styles.label}>Regole mercato</Text>
          <Text style={styles.label}>Rimborso svincolo volontario (%)</Text>
          <TextInput
            value={voluntaryRefundText}
            onChangeText={setVoluntaryRefundText}
            keyboardType="number-pad"
            editable={canConfigure}
            style={styles.input}
            accessibilityLabel="Rimborso svincolo volontario (%)"
            testID="league-admin-voluntary-refund"
          />
          <Text style={styles.label}>Rimborso svincolo per uscita dai cinque campionati (%)</Text>
          <TextInput
            value={exitRefundText}
            onChangeText={setExitRefundText}
            keyboardType="number-pad"
            editable={canConfigure}
            style={styles.input}
            accessibilityLabel="Rimborso svincolo per uscita dai cinque campionati (%)"
            testID="league-admin-exit-refund"
          />
          <Text style={styles.label}>Proposte di scambio attive per squadra (max)</Text>
          <TextInput
            value={maxTradeProposalsText}
            onChangeText={setMaxTradeProposalsText}
            keyboardType="number-pad"
            editable={canConfigure}
            style={styles.input}
            accessibilityLabel="Proposte di scambio attive per squadra (max)"
            testID="league-admin-max-trade-proposals"
          />
          {saveSuccess ? (
            <UiStatePanel
              state="success"
              title="Regolamento salvato"
              message={saveSuccess}
              testID="league-admin-rules-saved"
            />
          ) : null}
          <Pressable
            accessibilityRole="button"
            disabled={!canConfigure || workingId === "rules"}
            onPress={() => void onSaveRules()}
            style={[styles.primaryButton, (!canConfigure || workingId === "rules") && styles.disabled]}
            testID="league-admin-save-rules"
          >
            <Text style={styles.primaryLabel}>Salva regolamento</Text>
          </Pressable>

            </>
          ) : null}
          {setupTab === "invitati" ? (
            <>
          <View style={styles.membersHeader}>
            <Text
              style={[styles.heading, styles.membersTitle]}
              numberOfLines={1}
              adjustsFontSizeToFit
              minimumFontScale={0.7}
            >
              Partecipanti iscritti
            </Text>
            <Pressable
              accessibilityRole="button"
              accessibilityLabel="Opzioni partecipanti"
              onPress={() => setMenuOpen(true)}
              style={styles.menuButton}
              testID="league-members-menu-open"
            >
              <Text style={styles.menuButtonGlyph}>⋯</Text>
            </Pressable>
          </View>
          {!canConfigure ? (
            <Text style={styles.body} testID="league-members-locked-hint">
              A stagione avviata si possono sostituire i fantallenatori e gestire gli
              amministratori; rimuovere un partecipante è possibile solo prima dell&apos;avvio.
            </Text>
          ) : null}
          <Text style={styles.body} testID="league-members-capacity">
            Iscritti: {members.length} / Previsti: {rules.participantCount}
            {pendingInviteCount > 0 ? ` · ${pendingInvitesLabel(pendingInviteCount)}` : ""}
          </Text>
          {members.length !== rules.participantCount ? (
            <UiStatePanel
              state="empty"
              title="Numero partecipanti non allineato"
              message={
                members.length < rules.participantCount
                  ? // Sotto il minimo il server rifiuta «Partecipanti»
                    // (invalid_participant_count): niente suggerimento di abbassarlo.
                    rules.participantMin == null || members.length >= rules.participantMin
                    ? `${missingMembersLabel(rules.participantCount - members.length)}, oppure abbassa «Partecipanti» a ${members.length} e salva.`
                    : `${missingMembersLabel(rules.participantCount - members.length)}.`
                  : `Ci sono più iscritti del previsto: alza «Partecipanti» a ${members.length} e salva.`
              }
              testID="league-members-mismatch"
            />
          ) : null}
          <View style={styles.memberList} testID="league-members-list">
            {members.map((member) => {
              const identity = (
                <>
                  <AvatarWithFallback
                    src={resolveAvatarUrl(member.avatarUrl ?? null)}
                    style={styles.memberAvatar}
                    fallback={
                      <View style={styles.memberAvatarFallback}>
                        <Text style={styles.memberAvatarInitial}>
                          {avatarInitials(member.displayName)}
                        </Text>
                      </View>
                    }
                  />
                  <View style={styles.flex}>
                    <Text style={styles.inviteTitle}>{member.displayName}</Text>
                    {member.email ? (
                      <Text style={styles.body} testID={`league-member-email-${member.userId}`}>
                        {member.email}
                      </Text>
                    ) : null}
                    <Text style={styles.body}>{memberRoleLabel(member)}</Text>
                  </View>
                </>
              );
              return (
                <View key={member.userId} style={styles.memberRow}>
                  {canOpenMemberProfile(member, user?.id) ? (
                    // Il nome apre il profilo del fantallenatore, come sul sito (1.5).
                    <Pressable
                      accessibilityRole="button"
                      accessibilityLabel={`Apri il profilo di ${member.displayName}`}
                      onPress={() =>
                        leagueId
                          ? navigation.navigate("CoachProfile", { userId: member.userId, leagueId })
                          : undefined
                      }
                      style={styles.memberIdentity}
                      testID={`league-member-open-${member.userId}`}
                    >
                      {identity}
                    </Pressable>
                  ) : (
                    <View style={styles.memberIdentity}>{identity}</View>
                  )}
                  {canManageMember(member, canConfigure) ? (
                    <View style={styles.row}>
                      {canAssignRandomRoster(member, canConfigure) ? (
                        <Pressable
                          accessibilityRole="button"
                          disabled={workingId !== null}
                          onPress={() => void onAssignRandomRoster(member)}
                          style={[styles.secondaryButton, workingId !== null && styles.disabled]}
                          testID={`league-members-random-ai-${member.userId}`}
                        >
                          <Text style={styles.secondaryLabel}>
                            {workingId === `random-${member.userId}`
                              ? "Assegnazione…"
                              : "Assegna rosa random"}
                          </Text>
                        </Pressable>
                      ) : null}
                      <Pressable
                        accessibilityRole="button"
                        disabled={workingId !== null}
                        onPress={() => setRemoveTarget(member)}
                        style={[styles.dangerButton, workingId !== null && styles.disabled]}
                        testID={`league-member-remove-${member.userId}`}
                      >
                        <Text style={styles.dangerLabel}>Rimuovi</Text>
                      </Pressable>
                    </View>
                  ) : null}
                </View>
              );
            })}
          </View>
          {membersSuccess ? (
            <UiStatePanel
              state="success"
              title="Partecipanti aggiornati"
              message={membersSuccess}
              testID="league-members-success"
            />
          ) : null}

          <Text style={styles.heading}>Directory fantallenatori</Text>
          {leagueId ? (
            <CoachDirectoryPanel
              leagueId={leagueId}
              capacity={rules.participantCount}
              memberCount={members.length}
              pendingInviteCount={pendingInviteCount}
              testIDPrefix="league-admin-directory"
              onMembershipChanged={() => void loadAll({ silent: true })}
              onInvitesChanged={() => setInvitesReload((current) => current + 1)}
            />
          ) : null}

          <Text style={styles.heading}>Inviti tramite link o codice</Text>
          <Text style={styles.body}>
            Le leghe sono private: condividi il link oppure il codice. Non esiste una ricerca
            pubblica.
          </Text>
          <View style={styles.row}>
            {[1, 7, 14, 30].map((days) => (
              <Pressable
                key={days}
                accessibilityRole="button"
                onPress={() => setExpiresInDays(days)}
                style={[
                  styles.seasonChip,
                  expiresInDays === days && styles.seasonChipSelected,
                ]}
              >
                <Text
                  style={[
                    styles.seasonLabel,
                    expiresInDays === days && styles.seasonLabelSelected,
                  ]}
                >
                  {days}g
                </Text>
              </Pressable>
            ))}
          </View>
          <Pressable
            accessibilityRole="button"
            onPress={() => void onCreateInvite()}
            style={styles.primaryButton}
            testID="league-invite-create"
          >
            <Text style={styles.primaryLabel}>
              {workingId === "create-invite" ? "Generazione…" : "Genera invito"}
            </Text>
          </Pressable>

          {createdInvite ? (
            <View style={styles.section} testID="league-invite-secrets">
              <UiStatePanel
                state="success"
                title="Invito generato"
                message="Copia ora link e codice: per sicurezza non saranno mostrati di nuovo."
                testID="league-invite-created"
              />
              <Text style={styles.label}>Codice</Text>
              <Text style={styles.inviteTitle} testID="league-invite-code">
                {createdInvite.code}
              </Text>
              <Text style={styles.label}>Link</Text>
              <Text style={styles.body} testID="league-invite-url">
                {createdInvite.inviteUrl}
              </Text>
              <View style={styles.row}>
                <Pressable
                  accessibilityRole="button"
                  onPress={() => void onCopy(createdInvite.inviteUrl, "Link")}
                  style={styles.secondaryButton}
                  testID="league-invite-copy-url"
                >
                  <Text style={styles.secondaryLabel}>Copia link</Text>
                </Pressable>
                <Pressable
                  accessibilityRole="button"
                  onPress={() => void onCopy(createdInvite.code, "Codice")}
                  style={styles.secondaryButton}
                  testID="league-invite-copy-code"
                >
                  <Text style={styles.secondaryLabel}>Copia codice</Text>
                </Pressable>
              </View>
              {copyFeedback ? (
                <UiStatePanel
                  state="success"
                  title="Copiato"
                  message={copyFeedback}
                  testID="league-invite-copy-success"
                />
              ) : null}
              {copyError ? (
                <UiStatePanel
                  state="error"
                  title="Copia non riuscita"
                  message={copyError}
                  testID="league-invite-copy-error"
                />
              ) : null}
            </View>
          ) : null}

          {invites.length === 0 ? (
            <UiStatePanel
              state="empty"
              title="Nessun invito"
              message="Genera il primo invito per aggiungere partecipanti."
              testID="league-invites-empty"
            />
          ) : (
            <View testID="league-invites-list">
              {invites.map((invite) => (
                <View key={invite.id} style={styles.inviteRow}>
                  <View style={styles.flex}>
                    <Text style={styles.inviteTitle}>
                      {invite.status === "active"
                        ? "Attivo"
                        : invite.status === "revoked"
                          ? "Revocato"
                          : "Scaduto"}
                    </Text>
                    <Text style={styles.body}>Scade {formatDate(invite.expiresAt)}</Text>
                  </View>
                  {invite.status === "active" ? (
                    <Pressable
                      accessibilityRole="button"
                      onPress={() => void onRevoke(invite.id)}
                      style={styles.dangerButton}
                      testID="league-invite-revoke"
                    >
                      <Text style={styles.dangerLabel}>Revoca</Text>
                    </Pressable>
                  ) : null}
                </View>
              ))}
            </View>
          )}

            </>
          ) : null}

          {isLeagueDeletable(currentState) ? (
            <View style={styles.section} testID="league-delete-panel">
              <Text style={styles.heading}>Elimina lega</Text>
              <Text style={styles.body}>
                Disponibile solo in bozza o configurazione iniziale. Dopo l'avvio stagione usa
                «Archivia lega». L'operazione è definitiva.
              </Text>
              <Pressable
                accessibilityRole="checkbox"
                accessibilityState={{ checked: deleteConfirmed }}
                accessibilityLabel={`Confermo di voler eliminare definitivamente ${leagueName}`}
                onPress={() => setDeleteConfirmed((value) => !value)}
                style={styles.checkboxRow}
                testID="league-delete-confirm"
              >
                <View style={[styles.checkbox, deleteConfirmed && styles.checkboxChecked]} />
                <Text style={styles.body}>
                  Confermo di voler eliminare definitivamente «{leagueName}»
                </Text>
              </Pressable>
              {deleteSuccess ? (
                <UiStatePanel
                  state="success"
                  title="Lega eliminata"
                  message={deleteSuccess}
                  testID="league-delete-success"
                />
              ) : null}
              <Pressable
                accessibilityRole="button"
                disabled={!deleteConfirmed || workingId === "delete"}
                onPress={() => void onDelete()}
                style={[
                  styles.dangerButton,
                  (!deleteConfirmed || workingId === "delete") && styles.disabled,
                ]}
                testID="league-delete-submit"
              >
                <Text style={styles.dangerLabel}>Elimina lega</Text>
              </Pressable>
            </View>
          ) : (
            <UiStatePanel
              state="empty"
              title="Eliminazione non disponibile"
              message="Dopo l'avvio stagione usa Archivia lega invece dell'eliminazione definitiva."
              testID="league-delete-unavailable"
            />
          )}
        </View>
      ) : null}
      <Modal
        visible={menuOpen}
        transparent
        animationType="slide"
        onRequestClose={() => setMenuOpen(false)}
      >
        <Pressable style={styles.sheetOverlay} onPress={() => setMenuOpen(false)}>
          <Pressable style={styles.sheet} onPress={() => undefined} testID="league-members-menu">
            <View style={styles.sheetHandle} />
            <Text style={styles.inviteTitle}>Gestisci partecipanti</Text>
            <Pressable
              accessibilityRole="button"
              onPress={() => {
                setMenuOpen(false);
                openReplace();
              }}
              style={styles.sheetOption}
              testID="league-members-replace-open"
            >
              <View style={styles.sheetIcon}>
                <Text style={styles.sheetIconGlyph}>⇄</Text>
              </View>
              <View style={styles.flex}>
                <Text style={styles.inviteTitle}>Sostituisci fantallenatore</Text>
                <Text style={styles.body}>
                  Al posto di chi lascia entra un altro, con squadra, rosa e punti.
                </Text>
              </View>
            </Pressable>
            <Pressable
              accessibilityRole="button"
              onPress={() => {
                setMenuOpen(false);
                openAdmin();
              }}
              style={styles.sheetOption}
              testID="league-members-admin-open"
            >
              <View style={styles.sheetIcon}>
                <Text style={styles.sheetIconGlyph}>★</Text>
              </View>
              <View style={styles.flex}>
                <Text style={styles.inviteTitle}>Amministratori</Text>
                <Text style={styles.body}>
                  Passa il controllo a un altro o condividilo come co-amministratore.
                </Text>
              </View>
            </Pressable>
          </Pressable>
        </Pressable>
      </Modal>

      <Modal
        visible={adminOpen}
        transparent
        animationType="fade"
        onRequestClose={() => setAdminOpen(false)}
      >
        <DialogFrame
          title="Amministratori della lega"
          onClose={() => setAdminOpen(false)}
          testID="league-members-admin-panel"
          footer={
            <>
              <Pressable
                accessibilityRole="button"
                onPress={() => setAdminOpen(false)}
                style={styles.dialogGhost}
              >
                <Text style={styles.dialogGhostLabel}>Chiudi</Text>
              </Pressable>
              <Pressable
                accessibilityRole="button"
                disabled={!adminTargetId || workingId === "admin"}
                onPress={() => void onConfirmAdmin()}
                style={[styles.dialogPrimary, (!adminTargetId || workingId === "admin") && styles.disabled]}
                testID="league-members-admin-confirm"
              >
                <Text style={styles.primaryLabel}>{workingId === "admin" ? "Salvataggio…" : "Conferma"}</Text>
              </Pressable>
            </>
          }
        >
          <Text style={styles.dialogSection}>Amministratori attuali</Text>
          {members
            .filter((member) => member.role === "league_admin")
            .map((admin) => {
              const admins = members.filter((member) => member.role === "league_admin");
              const isMe = !!user && admin.userId === user.id;
              return (
                <View key={admin.userId} style={styles.dialogRow}>
                  <Text style={[styles.inviteTitle, styles.flex]} numberOfLines={1}>
                    {admin.displayName}
                    {isMe ? " (tu)" : ""}
                  </Text>
                  {admins.length > 1 && !isMe ? (
                    <Pressable
                      accessibilityRole="button"
                      disabled={workingId !== null}
                      onPress={() => void onRevokeAdmin(admin.userId)}
                      style={styles.dialogSmall}
                      testID={`league-members-admin-revoke-${admin.userId}`}
                    >
                      <Text style={styles.secondaryLabel}>Togli ruolo</Text>
                    </Pressable>
                  ) : null}
                </View>
              );
            })}
          <Text style={styles.dialogSection}>Aggiungi o passa il ruolo</Text>
          <Text style={styles.label}>Chi diventa amministratore</Text>
          {members
            .filter((member) => member.role === "member")
            .map((member) => (
              <RadioRow
                key={member.userId}
                selected={adminTargetId === member.userId}
                onPress={() => setAdminTargetId(member.userId)}
                title={member.displayName}
                testID={`league-members-admin-target-${member.userId}`}
              />
            ))}
          <Text style={styles.label}>Come</Text>
          <RadioRow
            selected={adminMode === "co_admin"}
            onPress={() => setAdminMode("co_admin")}
            title="Condividi il controllo"
            subtitle="Restate entrambi amministratori."
            testID="league-members-admin-mode-co"
          />
          <RadioRow
            selected={adminMode === "transfer"}
            onPress={() => setAdminMode("transfer")}
            title="Passa il controllo"
            subtitle="Tu torni a essere un partecipante."
            testID="league-members-admin-mode-transfer"
          />
          {adminError ? (
            <Text style={[styles.body, styles.replaceError]} testID="league-members-admin-error">
              {adminError}
            </Text>
          ) : null}
        </DialogFrame>
      </Modal>

      <Modal
        visible={replaceOpen}
        transparent
        animationType="fade"
        onRequestClose={() => setReplaceOpen(false)}
      >
        <DialogFrame
          title="Sostituisci fantallenatore"
          onClose={() => setReplaceOpen(false)}
          testID="league-members-replace-panel"
          footer={
            <>
              <Pressable
                accessibilityRole="button"
                onPress={() => setReplaceOpen(false)}
                style={styles.dialogGhost}
              >
                <Text style={styles.dialogGhostLabel}>Annulla</Text>
              </Pressable>
              <Pressable
                accessibilityRole="button"
                disabled={!replaceFromId || !replaceToId || workingId === "replace"}
                onPress={() => void onReplace()}
                style={[
                  styles.dialogPrimary,
                  (!replaceFromId || !replaceToId || workingId === "replace") && styles.disabled,
                ]}
                testID="league-members-replace-confirm"
              >
                <Text style={styles.primaryLabel}>
                  {workingId === "replace" ? "Sostituzione…" : "Sostituisci"}
                </Text>
              </Pressable>
            </>
          }
        >
          <Text style={styles.dialogSection}>1. Chi vuoi togliere</Text>
          {members
            .filter((member) => member.role === "member")
            .map((member) => (
              <RadioRow
                key={member.userId}
                selected={replaceFromId === member.userId}
                onPress={() => setReplaceFromId(member.userId)}
                title={member.displayName}
                testID={`league-members-replace-from-${member.userId}`}
              />
            ))}
          <Text style={styles.dialogSection}>2. Chi vuoi mettere</Text>
          <AppTextInput
            value={replaceQuery}
            onChangeText={setReplaceQuery}
            placeholder="Cerca per nome o nickname"
            autoCapitalize="none"
            autoCorrect={false}
            testID="league-members-replace-query"
          />
          {candidatesLoading ? <Text style={styles.body}>Ricerca in corso…</Text> : null}
          {!candidatesLoading && candidates.length === 0 ? (
            <Text style={styles.body} testID="league-members-replace-empty">
              Nessun fantallenatore disponibile: chi vuoi aggiungere deve aver già fatto
              l&apos;accesso ed essere disponibile agli inviti.
            </Text>
          ) : (
            candidates.map((candidate) => (
              <RadioRow
                key={candidate.userId}
                selected={replaceToId === candidate.userId}
                onPress={() => setReplaceToId(candidate.userId)}
                title={candidate.displayName}
                testID={`league-members-replace-pick-${candidate.userId}`}
              />
            ))
          )}
          {replaceFromId && replaceToId ? (
            <Text style={styles.body}>
              Chi subentra eredita squadra, rosa, formazioni e punti di chi viene tolto.
            </Text>
          ) : null}
          {replaceError ? (
            <Text style={[styles.body, styles.replaceError]} testID="league-members-replace-error">
              {replaceError}
            </Text>
          ) : null}
        </DialogFrame>
      </Modal>
      <ConfirmDialog
        copy={removeTarget ? removeMemberConfirmation(removeTarget.displayName, removalCounts()) : null}
        destructive
        busy={workingId !== null}
        onCancel={() => setRemoveTarget(null)}
        onConfirm={() => {
          const target = removeTarget;
          setRemoveTarget(null);
          if (target) {
            void onRemove(target.userId, target.displayName);
          }
        }}
        testID="league-member-remove-confirm-dialog"
      />
      <CalendarActionDialog
        state={calendarModal}
        working={workingId === "calendar-generate" || workingId === "calendar-confirm"}
        onCancel={closeCalendarModal}
        onProceed={(force) => {
          if (calendarModal) {
            void runCalendarAction(calendarModal.action, force);
          }
        }}
      />
    </PageContainer>
  );
}

/** Finestra come la modale del web: intestazione con titolo e chiusura, corpo scorrevole, piè di pagina con i bottoni. */
function DialogFrame({
  title,
  onClose,
  footer,
  children,
  testID,
}: {
  title: string;
  onClose: () => void;
  footer: ReactNode;
  children: ReactNode;
  testID?: string;
}) {
  return (
    <View style={styles.replaceOverlay}>
      <View style={styles.dialogBox} testID={testID}>
        <View style={styles.dialogHeader}>
          <Text style={styles.dialogTitle} numberOfLines={2}>
            {title}
          </Text>
          <Pressable
            accessibilityRole="button"
            accessibilityLabel="Chiudi"
            onPress={onClose}
            style={styles.dialogClose}
            hitSlop={8}
          >
            <Text style={styles.dialogCloseLabel}>✕</Text>
          </Pressable>
        </View>
        <ScrollView style={styles.dialogScroll} contentContainerStyle={styles.dialogBody} keyboardShouldPersistTaps="handled">
          {children}
        </ScrollView>
        <View style={styles.dialogFooter}>{footer}</View>
      </View>
    </View>
  );
}

function RadioRow({
  selected,
  onPress,
  title,
  subtitle,
  testID,
}: {
  selected: boolean;
  onPress: () => void;
  title: string;
  subtitle?: string;
  testID?: string;
}) {
  return (
    <Pressable
      accessibilityRole="radio"
      accessibilityState={{ selected }}
      onPress={onPress}
      style={[styles.dialogRow, selected && styles.dialogRowSelected]}
      testID={testID}
    >
      <View style={[styles.radio, selected && styles.radioOn]}>{selected ? <View style={styles.radioDot} /> : null}</View>
      <View style={styles.flex}>
        <Text style={styles.inviteTitle} numberOfLines={1}>
          {title}
        </Text>
        {subtitle ? (
          <Text style={styles.body} numberOfLines={1}>
            {subtitle}
          </Text>
        ) : null}
      </View>
    </Pressable>
  );
}

const styles = lazyStyles(() => StyleSheet.create({
  content: {
    gap: spacing.sm,
  },
  section: {
    gap: spacing.sm,
    marginTop: spacing.sm,
  },
  heading: {
    marginTop: spacing.lg,
    color: colors.foreground,
    fontSize: typography.fontSize.xl,
    fontWeight: typography.fontWeight.semibold,
  },
  body: {
    color: colors.foregroundMuted,
    fontSize: typography.fontSize.sm,
  },
  label: {
    color: colors.foregroundMuted,
    fontSize: typography.fontSize.sm,
    fontWeight: typography.fontWeight.semibold,
  },
  input: {
    minHeight: 44,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.md,
    paddingHorizontal: spacing.md,
    color: colors.foreground,
    backgroundColor: colors.backgroundElevated,
  },
  switchLabel: {
    flex: 1,
    paddingRight: spacing.sm,
  },
  switchRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
  },
  row: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacing.sm,
  },
  flex: {
    flex: 1,
  },
  memberList: {
    gap: spacing.sm,
  },
  membersHeader: {
    marginTop: spacing.lg,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: spacing.sm,
  },
  membersTitle: {
    flex: 1,
    marginTop: 0,
  },
  menuButton: {
    width: 44,
    height: 44,
    borderRadius: 22,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.backgroundElevated,
    alignItems: "center",
    justifyContent: "center",
  },
  menuButtonGlyph: {
    color: colors.accent,
    fontSize: 24,
    lineHeight: 26,
    fontWeight: typography.fontWeight.semibold,
  },
  sheetOverlay: {
    flex: 1,
    justifyContent: "flex-end",
    backgroundColor: "rgba(0,0,0,0.55)",
  },
  sheet: {
    gap: spacing.sm,
    padding: spacing.lg,
    paddingBottom: spacing.xl,
    borderTopLeftRadius: 24,
    borderTopRightRadius: 24,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.backgroundElevated,
  },
  sheetHandle: {
    alignSelf: "center",
    width: 40,
    height: 4,
    borderRadius: 2,
    marginBottom: spacing.sm,
    backgroundColor: colors.border,
  },
  sheetOption: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.md,
    padding: spacing.md,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.background,
  },
  sheetIcon: {
    width: 44,
    height: 44,
    borderRadius: 22,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.brand,
  },
  sheetIconGlyph: {
    color: colors.onBrand,
    fontSize: 20,
    fontWeight: typography.fontWeight.semibold,
  },
  replaceOverlay: {
    flex: 1,
    justifyContent: "center",
    padding: spacing.lg,
    backgroundColor: "rgba(0,0,0,0.6)",
  },
  replaceBox: {
    maxHeight: "90%",
    gap: spacing.sm,
    padding: spacing.lg,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.backgroundElevated,
  },
  dialogBox: {
    maxHeight: "92%",
    borderRadius: radius.lg,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.backgroundElevated,
    overflow: "hidden",
  },
  dialogHeader: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: spacing.md,
    padding: spacing.md,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  dialogTitle: {
    flex: 1,
    color: colors.foreground,
    fontSize: typography.fontSize.lg,
    fontWeight: typography.fontWeight.semibold,
  },
  dialogClose: {
    width: 36,
    height: 36,
    borderRadius: 18,
    alignItems: "center",
    justifyContent: "center",
    borderWidth: 1,
    borderColor: colors.border,
  },
  dialogCloseLabel: { color: colors.foreground, fontSize: 14 },
  dialogScroll: { flexGrow: 0 },
  dialogBody: { padding: spacing.md, gap: spacing.xs },
  dialogSection: {
    marginTop: spacing.sm,
    color: colors.foreground,
    fontSize: typography.fontSize.md,
    fontWeight: typography.fontWeight.semibold,
  },
  dialogRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
    paddingVertical: spacing.sm,
    paddingHorizontal: spacing.md,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.md,
  },
  dialogRowSelected: { borderColor: colors.accent, borderWidth: 2 },
  radio: {
    width: 20,
    height: 20,
    borderRadius: 10,
    borderWidth: 2,
    borderColor: colors.border,
    alignItems: "center",
    justifyContent: "center",
  },
  radioOn: { borderColor: colors.accent },
  radioDot: { width: 10, height: 10, borderRadius: 5, backgroundColor: colors.accent },
  dialogSmall: {
    minHeight: 36,
    paddingHorizontal: spacing.md,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.pill,
    alignItems: "center",
    justifyContent: "center",
  },
  dialogFooter: {
    flexDirection: "row",
    justifyContent: "flex-end",
    gap: spacing.sm,
    padding: spacing.md,
    borderTopWidth: 1,
    borderTopColor: colors.border,
  },
  dialogGhost: {
    minHeight: 44,
    paddingHorizontal: spacing.lg,
    borderRadius: radius.pill,
    alignItems: "center",
    justifyContent: "center",
  },
  dialogGhostLabel: { color: colors.foreground, fontWeight: typography.fontWeight.semibold },
  dialogPrimary: {
    minHeight: 44,
    paddingHorizontal: spacing.lg,
    borderRadius: radius.pill,
    backgroundColor: colors.brand,
    alignItems: "center",
    justifyContent: "center",
  },
  replaceOption: {
    marginTop: spacing.xs,
    padding: spacing.md,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.md,
  },
  replaceError: {
    color: colors.danger,
  },
  replaceOptionSelected: {
    borderColor: colors.accent,
    borderWidth: 2,
  },
  primaryButton: {
    minHeight: 44,
    padding: spacing.md,
    borderRadius: radius.pill,
    backgroundColor: colors.brand,
    alignItems: "center",
    justifyContent: "center",
  },
  primaryLabel: {
    color: colors.onBrand,
    fontWeight: typography.fontWeight.semibold,
  },
  secondaryButton: {
    minHeight: 44,
    padding: spacing.sm,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.pill,
    alignItems: "center",
    justifyContent: "center",
  },
  secondaryLabel: {
    color: colors.accent,
    fontWeight: typography.fontWeight.semibold,
  },
  inviteRow: {
    marginTop: spacing.sm,
    padding: spacing.md,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.md,
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    gap: spacing.sm,
  },
  inviteTitle: {
    color: colors.foreground,
    fontWeight: typography.fontWeight.semibold,
  },
  memberRow: {
    padding: spacing.md,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.md,
    gap: spacing.sm,
  },
  memberIdentity: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
  },
  memberAvatar: {
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: colors.border,
  },
  memberAvatarFallback: {
    width: 40,
    height: 40,
    borderRadius: 20,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.border,
  },
  memberAvatarInitial: {
    color: colors.foreground,
    fontWeight: typography.fontWeight.semibold,
  },
  dangerButton: {
    minHeight: 44,
    padding: spacing.sm,
    borderWidth: 1,
    borderColor: colors.danger,
    borderRadius: radius.pill,
    alignItems: "center",
    justifyContent: "center",
  },
  dangerLabel: {
    color: colors.danger,
    fontWeight: typography.fontWeight.semibold,
  },
  seasonChip: {
    minHeight: 40,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    borderRadius: radius.pill,
    borderWidth: 1,
    borderColor: colors.border,
    justifyContent: "center",
  },
  seasonChipSelected: {
    borderColor: colors.accent,
  },
  seasonLabel: {
    color: colors.foregroundMuted,
  },
  seasonLabelSelected: {
    color: colors.accent,
    fontWeight: typography.fontWeight.semibold,
  },
  checkboxRow: {
    flexDirection: "row",
    alignItems: "flex-start",
    gap: spacing.sm,
  },
  checkbox: {
    width: 22,
    height: 22,
    marginTop: 2,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 4,
  },
  checkboxChecked: {
    backgroundColor: colors.accent,
    borderColor: colors.accent,
  },
  disabled: {
    opacity: 0.5,
  },
}));
