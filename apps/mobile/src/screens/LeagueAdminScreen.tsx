import type {
  CreatedLeagueInvite,
  LeagueCalendar,
  LeagueInvite,
  LeagueLifecycle,
  LeagueMember,
  LeagueRules,
  LeagueState,
  UpdateLeagueRulesRequest,
} from "@fantappero/contracts";
import { theme } from "@fantappero/ui/theme";
import { useNavigation, useRoute, type RouteProp } from "@react-navigation/core";
import type { NativeStackNavigationProp } from "@react-navigation/native-stack";
import { useCallback, useEffect, useState } from "react";
import { Pressable, StyleSheet, Switch, Text, TextInput, View } from "react-native";
import {
  confirmLeagueCalendar,
  createLeagueInvite,
  deleteLeague,
  fetchLeagueAdminPanel,
  fetchLeagueCalendarAdmin,
  fetchLeagueInvites,
  fetchLeagueMembers,
  generateLeagueCalendar,
  removeLeagueMember,
  revokeLeagueInvite,
  transferLeagueAdmin,
  transitionLeagueState,
  updateLeagueRules,
} from "../api/leagues";
import { CoachDirectoryPanel } from "../components/CoachDirectoryPanel";
import { UiStatePanel } from "../components/UiStatePanel";
import { useScreenData } from "../hooks/useScreenData";
import { PageContainer } from "../layout/PageContainer";
import { isLeagueDeletable } from "../leagues/leagueDeleteHelpers";
import { leagueStateLabel } from "../leagues/leagueLabels";
import type { RootStackParamList } from "../navigation/types";
import { getApiErrorMessage, useAuthSession } from "../session/DemoSessionContext";
import { copyToClipboard } from "../utils/clipboard";

const { colors, spacing, typography, radius } = theme;


function buildPayloadFromRules(rules: LeagueRules): UpdateLeagueRulesRequest {
  return {
    presetName: rules.presetName,
    participantCount: rules.participantCount,
    roster: { ...rules.roster },
    totalCredits: rules.totalCredits,
    minFixturesPerRound: rules.minFixturesPerRound,
    minutesThreshold: rules.minutesThreshold,
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
  const [invites, setInvites] = useState<LeagueInvite[]>([]);
  const [createdInvite, setCreatedInvite] = useState<CreatedLeagueInvite | null>(null);
  const [calendar, setCalendar] = useState<LeagueCalendar | null>(null);
  const [expiresInDays, setExpiresInDays] = useState(7);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [saveSuccess, setSaveSuccess] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [workingId, setWorkingId] = useState<string | null>(null);
  const [copyFeedback, setCopyFeedback] = useState<string | null>(null);
  const [copyError, setCopyError] = useState<string | null>(null);
  const [deleteConfirmed, setDeleteConfirmed] = useState(false);
  const [deleteSuccess, setDeleteSuccess] = useState<string | null>(null);
  const [participantCountText, setParticipantCountText] = useState("8");
  const [minutesThresholdText, setMinutesThresholdText] = useState("15");

  const loadAll = useCallback(
    async (options?: { silent?: boolean }) => {
      setActionError(null);
      setSaveSuccess(false);
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
        setParticipantCountText(String(panel.rules.participantCount));
        setMinutesThresholdText(String(panel.rules.minutesThreshold));
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
    setSaveSuccess(false);
    const nextRules: LeagueRules = {
      ...rules,
      participantCount: Number(participantCountText) || rules.participantCount,
      minutesThreshold: Number(minutesThresholdText) || rules.minutesThreshold,
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
      setSaveSuccess(true);
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

  async function onTransfer(userId: string, displayName: string) {
    setActionError(null);
    if (!leagueId || !accessToken) {
      return;
    }
    setWorkingId(`transfer-${userId}`);
    try {
      await transferLeagueAdmin(accessToken, leagueId, userId);
      setMembers(await fetchLeagueMembers(accessToken, leagueId));
    } catch (error) {
      setActionError(
        getApiErrorMessage(error, `Impossibile trasferire il ruolo a ${displayName}.`),
      );
    } finally {
      setWorkingId(null);
    }
  }

  async function onRemove(userId: string, displayName: string) {
    setActionError(null);
    if (!leagueId || !accessToken) {
      return;
    }
    setWorkingId(`remove-${userId}`);
    try {
      await removeLeagueMember(accessToken, leagueId, userId);
      setMembers((current) => current.filter((row) => row.userId !== userId));
    } catch (error) {
      setActionError(getApiErrorMessage(error, `Impossibile rimuovere ${displayName}.`));
    } finally {
      setWorkingId(null);
    }
  }

  async function onGenerateCalendar() {
    setActionError(null);
    if (!leagueId || !accessToken) {
      return;
    }
    setWorkingId("calendar-generate");
    try {
      setCalendar(await generateLeagueCalendar(accessToken, leagueId));
    } catch (error) {
      setActionError(getApiErrorMessage(error, "Impossibile generare il calendario."));
    } finally {
      setWorkingId(null);
    }
  }

  async function onConfirmCalendar() {
    setActionError(null);
    if (!leagueId || !accessToken) {
      return;
    }
    setWorkingId("calendar-confirm");
    try {
      setCalendar(await confirmLeagueCalendar(accessToken, leagueId));
    } catch (error) {
      setActionError(getApiErrorMessage(error, "Impossibile confermare il calendario."));
    } finally {
      setWorkingId(null);
    }
  }

  async function onTransition(targetState: LeagueState) {
    setActionError(null);
    if (!leagueId || !accessToken) {
      return;
    }
    setWorkingId(`transition-${targetState}`);
    try {
      setLifecycle(await transitionLeagueState(accessToken, leagueId, { targetState }));
      try {
        await refreshMemberships();
      } catch {
        // Transizione già riuscita.
      }
    } catch (error) {
      setActionError(getApiErrorMessage(error, "Impossibile aggiornare lo stato della lega."));
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
      navigation.navigate("MainTabs", { screen: "Leagues" } as never);
    } catch (error) {
      setActionError(getApiErrorMessage(error, "Impossibile eliminare la lega."));
    } finally {
      setWorkingId(null);
    }
  }

  const canConfigure =
    lifecycle?.state === "draft" || lifecycle?.state === "configuring";
  const leagueName = activeLeague?.name ?? "Lega";
  const currentState = lifecycle?.state ?? "draft";

  return (
    <PageContainer
      title="Amministrazione lega"
      testID="screen-league-admin"
      refreshing={refreshing}
      onRefresh={onRefresh}
    >
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
        <View style={styles.content}>
          <Text style={styles.heading}>Regolamento</Text>
          <Text style={styles.body}>Preset standard (fisso in M1)</Text>
          <Text style={styles.label}>Partecipanti previsti</Text>
          <TextInput
            value={participantCountText}
            onChangeText={setParticipantCountText}
            keyboardType="number-pad"
            editable={canConfigure}
            style={styles.input}
            accessibilityLabel="Partecipanti previsti"
            testID="league-admin-participant-count"
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
          <View style={styles.switchRow}>
            <Text style={styles.body}>Scambi consentiti</Text>
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
            <Text style={styles.body}>Inviti manuali</Text>
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
          {saveSuccess ? (
            <UiStatePanel
              state="success"
              title="Regolamento salvato"
              message="Le modifiche sono state applicate."
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

          <Text style={styles.heading}>Partecipanti iscritti</Text>
          <View style={styles.memberList} testID="league-members-list">
            {members.map((member) => (
              <View key={member.userId} style={styles.inviteRow}>
                <View style={styles.flex}>
                  <Text style={styles.inviteTitle}>{member.displayName}</Text>
                  <Text style={styles.body}>
                    {member.role === "league_admin" ? "Amministratore" : "Partecipante"}
                  </Text>
                </View>
                {member.role === "member" ? (
                  <View style={styles.row}>
                    <Pressable
                      accessibilityRole="button"
                      onPress={() => void onTransfer(member.userId, member.displayName)}
                      style={styles.secondaryButton}
                      testID={`league-member-transfer-${member.userId}`}
                    >
                      <Text style={styles.secondaryLabel}>Trasferisci admin</Text>
                    </Pressable>
                    <Pressable
                      accessibilityRole="button"
                      onPress={() => void onRemove(member.userId, member.displayName)}
                      style={styles.dangerButton}
                      testID={`league-member-remove-${member.userId}`}
                    >
                      <Text style={styles.dangerLabel}>Rimuovi</Text>
                    </Pressable>
                  </View>
                ) : null}
              </View>
            ))}
          </View>

          <Text style={styles.heading}>Calendario scontri diretti</Text>
          <View style={styles.section} testID="league-calendar-panel">
            <Text style={styles.body}>
              {calendar?.status === "confirmed"
                ? `Calendario confermato: ${calendar.roundCount} giornate.`
                : calendar
                  ? `Anteprima: ${calendar.matchupCount} incontri su ${calendar.roundCount} turni.`
                  : "Genera un girone di andata bilanciato prima dell'avvio stagione."}
            </Text>
            <Pressable
              accessibilityRole="button"
              onPress={() => void onGenerateCalendar()}
              style={styles.primaryButton}
              testID="league-calendar-generate"
            >
              <Text style={styles.primaryLabel}>Genera anteprima</Text>
            </Pressable>
            {calendar && calendar.status !== "confirmed" ? (
              <Pressable
                accessibilityRole="button"
                onPress={() => void onConfirmCalendar()}
                style={styles.secondaryButton}
                testID="league-calendar-confirm"
              >
                <Text style={styles.secondaryLabel}>Conferma calendario</Text>
              </Pressable>
            ) : null}
          </View>

          <Text style={styles.heading}>Stato e avvio stagione</Text>
          <View style={styles.section} testID="league-season-panel">
            <Text style={styles.body}>Stato corrente: {leagueStateLabel(currentState)}</Text>
            {lifecycle.blockers.map((blocker) => (
              <Text key={blocker.code} style={styles.body}>
                · {blocker.message}
              </Text>
            ))}
            {lifecycle.allowedTransitions.map((target) => (
              <Pressable
                key={target}
                accessibilityRole="button"
                onPress={() => void onTransition(target)}
                style={styles.primaryButton}
                testID={`league-season-transition-${target}`}
              >
                <Text style={styles.primaryLabel}>
                  {target === "archived"
                    ? "Archivia lega"
                    : `Passa a ${leagueStateLabel(target)}`}
                </Text>
              </Pressable>
            ))}
          </View>

          <Text style={styles.heading}>Directory fantallenatori</Text>
          {leagueId ? (
            <CoachDirectoryPanel
              leagueId={leagueId}
              capacity={rules.participantCount}
              memberCount={members.length}
              testIDPrefix="league-admin-directory"
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
    </PageContainer>
  );
}

const styles = StyleSheet.create({
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
  primaryButton: {
    minHeight: 44,
    padding: spacing.md,
    borderRadius: radius.md,
    backgroundColor: colors.accent,
    alignItems: "center",
    justifyContent: "center",
  },
  primaryLabel: {
    color: colors.accentContrast,
    fontWeight: typography.fontWeight.semibold,
  },
  secondaryButton: {
    minHeight: 44,
    padding: spacing.sm,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.md,
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
  dangerButton: {
    minHeight: 44,
    padding: spacing.sm,
    borderWidth: 1,
    borderColor: colors.danger,
    borderRadius: radius.md,
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
    borderRadius: radius.md,
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
});
