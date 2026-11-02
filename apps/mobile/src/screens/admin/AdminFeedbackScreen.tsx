import {
  FEEDBACK_CATEGORY_LABEL,
  FEEDBACK_NOTE_MAX_CHARS,
  FEEDBACK_STATUSES,
  FEEDBACK_STATUS_LABEL,
  type FeedbackAdminList,
  type FeedbackAdminReport,
  type FeedbackStatus,
} from "@fantappero/contracts";
import { theme } from "@fantappero/ui/theme";
import { useNavigation } from "@react-navigation/core";
import type { NativeStackNavigationProp } from "@react-navigation/native-stack";
import { useCallback, useState } from "react";
import { Image, Linking, Modal, Pressable, StyleSheet, Text, View } from "react-native";
import { impersonateUser } from "../../api/admin";
import { ApiError, buildApiUrl } from "../../api/client";
import { fetchAdminFeedback, updateAdminFeedback } from "../../api/feedback";
import { adminUiStyles as styles } from "../../admin/adminUiStyles";
import { AppTextInput as TextInput } from "../../components/AppTextInput";
import { UiStatePanel } from "../../components/UiStatePanel";
import { impersonationTab } from "../../navigation/notificationDestination";
import { useScreenData } from "../../hooks/useScreenData";
import { PageContainer } from "../../layout/PageContainer";
import { leaveAdminForApp } from "../../navigation/adminEntry";
import type { RootStackParamList } from "../../navigation/types";
import { getApiErrorMessage, useAuthSession } from "../../session/DemoSessionContext";
import { lazyStyles } from "../../theme/lazyStyles";

const { colors, spacing, typography, radius } = theme;

const FILTERS: Array<{ id: FeedbackStatus | "all"; label: string }> = [
  { id: "all", label: "Tutte" },
  ...FEEDBACK_STATUSES.map((id) => ({ id, label: FEEDBACK_STATUS_LABEL[id] })),
];

const ACTIONS: Array<{ status: FeedbackStatus; label: string }> = [
  { status: "in_review", label: "Prendi in carico" },
  { status: "resolved", label: "Segna come risolta" },
  { status: "dismissed", label: "Chiudi" },
  { status: "new", label: "Riapri" },
];

function formatDate(value: string): string {
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

function ReportCard({
  report,
  accessToken,
  canImpersonate,
  onImpersonate,
  onChanged,
  onExpired,
}: {
  report: FeedbackAdminReport;
  accessToken: string;
  canImpersonate: boolean;
  onImpersonate: (report: FeedbackAdminReport) => void;
  onChanged: (next: FeedbackAdminReport) => void;
  onExpired: () => void;
}) {
  const [note, setNote] = useState(report.operatorNote ?? "");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function save(status?: FeedbackStatus) {
    setBusy(true);
    setError(null);
    try {
      onChanged(await updateAdminFeedback(accessToken, report.id, { status, operatorNote: note }));
    } catch (saveError) {
      setError(getApiErrorMessage(saveError, "Aggiornamento non riuscito."));
    } finally {
      setBusy(false);
    }
  }

  const noteChanged = note.trim() !== (report.operatorNote ?? "");
  return (
    <View style={styles.section} testID={`feedback-admin-${report.id}`}>
      <Text style={local.status}>{FEEDBACK_STATUS_LABEL[report.status]}</Text>
      <Text style={styles.sectionTitle}>{FEEDBACK_CATEGORY_LABEL[report.category]}</Text>
      <Text style={styles.meta}>
        {report.authorName} · {report.authorEmail}
      </Text>
      {canImpersonate ? (
        <Pressable
          accessibilityRole="button"
          onPress={() => onImpersonate(report)}
          style={local.secondary}
          testID={`feedback-admin-impersonate-${report.id}`}
        >
          <Text style={local.secondaryLabel}>Impersona</Text>
        </Pressable>
      ) : null}
      <Text style={styles.meta}>{formatDate(report.createdAt)}</Text>
      <Text style={local.message}>{report.message}</Text>

      {[
        ["Pagina", report.pageContext],
        ["Piattaforma", report.platform],
        ["Versione", report.appVersion],
        ["Dispositivo", report.userAgent],
      ].map(([label, value]) =>
        value ? (
          <Text key={label} style={styles.meta}>
            {label}: {value}
          </Text>
        ) : null,
      )}

      {report.attachments.map((attachment) => {
        const url = buildApiUrl(attachment.url);
        return attachment.kind === "image" ? (
          <Pressable
            key={attachment.id}
            accessibilityRole="imagebutton"
            accessibilityLabel="Apri l'immagine allegata"
            onPress={() => void Linking.openURL(url)}
          >
            <Image source={{ uri: url }} style={local.image} resizeMode="contain" onError={onExpired} />
          </Pressable>
        ) : (
          <Pressable
            key={attachment.id}
            accessibilityRole="button"
            onPress={() => void Linking.openURL(url)}
            style={local.videoButton}
            testID="feedback-admin-video"
          >
            <Text style={local.videoLabel}>▶ Guarda il video allegato</Text>
          </Pressable>
        );
      })}

      <TextInput
        value={note}
        onChangeText={setNote}
        multiline
        maxLength={FEEDBACK_NOTE_MAX_CHARS}
        placeholder="Nota interna (visibile solo agli operatori)"
        style={[styles.input, local.noteInput]}
        accessibilityLabel="Nota interna"
        testID={`feedback-admin-note-${report.id}`}
      />
      {error ? <UiStatePanel state="error" title="Non salvato" message={error} testID="feedback-admin-save-error" /> : null}
      {ACTIONS.filter((action) => action.status !== report.status).map((action) => (
        <Pressable
          key={action.status}
          accessibilityRole="button"
          disabled={busy}
          onPress={() => void save(action.status)}
          style={[action.status === "resolved" ? local.primary : local.secondary, busy && local.disabled]}
          testID={`feedback-admin-${action.status}-${report.id}`}
        >
          <Text style={action.status === "resolved" ? local.primaryLabel : local.secondaryLabel}>
            {action.label}
          </Text>
        </Pressable>
      ))}
      {noteChanged ? (
        <Pressable
          accessibilityRole="button"
          disabled={busy}
          onPress={() => void save()}
          style={[local.secondary, busy && local.disabled]}
        >
          <Text style={local.secondaryLabel}>Salva nota</Text>
        </Pressable>
      ) : null}
    </View>
  );
}

/** Pannello operatore: segnalazioni degli utenti con allegati e stato di lavorazione. */
export function AdminFeedbackScreen() {
  const { accessToken, user, startImpersonation } = useAuthSession();
  const navigation = useNavigation<NativeStackNavigationProp<RootStackParamList>>();
  const [pending, setPending] = useState<FeedbackAdminReport | null>(null);
  const [impersonating, setImpersonating] = useState(false);
  const [impersonationError, setImpersonationError] = useState<string | null>(null);
  const [filter, setFilter] = useState<FeedbackStatus | "all">("all");
  const [page, setPage] = useState(1);
  const [data, setData] = useState<FeedbackAdminList | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [expired, setExpired] = useState(false);

  const load = useCallback(async () => {
    if (!accessToken) {
      setError("Sessione non disponibile. Accedi di nuovo.");
      return;
    }
    try {
      setData(
        await fetchAdminFeedback(accessToken, {
          status: filter === "all" ? undefined : filter,
          page,
        }),
      );
      setError(null);
      setExpired(false);
    } catch (loadError) {
      setError(getApiErrorMessage(loadError, "Impossibile caricare le segnalazioni."));
    }
  }, [accessToken, filter, page]);

  const { refreshing, onRefresh } = useScreenData(load);

  async function confirmImpersonation() {
    if (!pending) {
      return;
    }
    if (!accessToken) {
      setImpersonationError("Sessione non disponibile. Accedi di nuovo.");
      setPending(null);
      return;
    }
    setImpersonating(true);
    setImpersonationError(null);
    try {
      const result = await impersonateUser(accessToken, pending.authorUserId);
      await startImpersonation(result);
      const tab = impersonationTab(pending.pageContext);
      setPending(null);
      leaveAdminForApp();
      // Si entra come l'utente nella schermata dove ha visto il problema.
      navigation.getParent()?.navigate("MainTabs", tab ? { screen: tab } : undefined);
    } catch (impersonateError) {
      if (impersonateError instanceof ApiError && impersonateError.code === "cannot_impersonate_self") {
        setImpersonationError("Non puoi impersonare te stesso.");
      } else if (impersonateError instanceof ApiError && impersonateError.status === 403) {
        setImpersonationError("Non hai i permessi per impersonare questo utente.");
      } else {
        setImpersonationError(getApiErrorMessage(impersonateError, "Impossibile impersonare l'utente."));
      }
      setPending(null);
    } finally {
      setImpersonating(false);
    }
  }

  const pages = data ? Math.max(1, Math.ceil(data.total / data.pageSize)) : 1;
  return (
    <PageContainer
      title="Segnalazioni degli utenti"
      testID="screen-admin-feedback"
      refreshing={refreshing}
      onRefresh={onRefresh}
    >
      {data ? (
        <Text style={local.count} testID="feedback-admin-new-count">
          {data.newCount === 0 ? "Nessuna segnalazione da leggere" : `${data.newCount} da leggere`}
        </Text>
      ) : null}
      <View style={local.filters}>
        {FILTERS.map((item) => (
          <Pressable
            key={item.id}
            accessibilityRole="button"
            accessibilityState={{ selected: filter === item.id }}
            onPress={() => {
              setFilter(item.id);
              setPage(1);
            }}
            style={[local.chip, filter === item.id && local.chipSelected]}
          >
            <Text style={[local.chipLabel, filter === item.id && local.chipLabelSelected]}>{item.label}</Text>
          </Pressable>
        ))}
      </View>

      {expired ? (
        <UiStatePanel
          state="empty"
          title="Allegato non disponibile"
          message="I link degli allegati durano pochi minuti. Trascina verso il basso per aggiornare."
          testID="feedback-admin-expired"
        />
      ) : null}
      {impersonationError ? (
        <UiStatePanel
          state="error"
          title="Impersonificazione non riuscita"
          message={impersonationError}
          testID="feedback-admin-impersonate-error"
        />
      ) : null}
      {error ? <UiStatePanel state="error" title="Errore di caricamento" message={error} testID="feedback-admin-error" /> : null}
      {data && data.items.length === 0 && !error ? (
        <UiStatePanel
          state="empty"
          title="Nessuna segnalazione"
          message="Quando un utente ne invia una, la trovi qui e ricevi una notifica."
          testID="feedback-admin-empty"
        />
      ) : null}
      {accessToken
        ? data?.items.map((report) => (
            <ReportCard
              key={report.id}
              report={report}
              accessToken={accessToken}
              canImpersonate={report.authorEmail !== "" && report.authorUserId !== user?.id}
              onImpersonate={setPending}
              onChanged={(next) => {
                setData((current) =>
                  current
                    ? { ...current, items: current.items.map((item) => (item.id === next.id ? next : item)) }
                    : current,
                );
                void load();
              }}
              onExpired={() => setExpired(true)}
            />
          ))
        : null}

      {data && pages > 1 ? (
        <View style={local.pager}>
          <Pressable
            accessibilityRole="button"
            disabled={page <= 1}
            onPress={() => setPage((value) => value - 1)}
            style={[local.secondary, page <= 1 && local.disabled]}
          >
            <Text style={local.secondaryLabel}>Precedente</Text>
          </Pressable>
          <Text style={styles.meta}>
            Pagina {page} di {pages}
          </Text>
          <Pressable
            accessibilityRole="button"
            disabled={page >= pages}
            onPress={() => setPage((value) => value + 1)}
            style={[local.secondary, page >= pages && local.disabled]}
          >
            <Text style={local.secondaryLabel}>Successiva</Text>
          </Pressable>
        </View>
      ) : null}

      <Modal
        visible={pending !== null}
        transparent
        animationType="fade"
        onRequestClose={() => setPending(null)}
      >
        <View style={styles.confirmOverlay}>
          {pending ? (
            <View style={styles.confirmBox} testID="feedback-admin-impersonate-box">
              <Text style={styles.sectionTitle}>Impersona utente</Text>
              <Text style={styles.meta}>
                {`Accederai come ${pending.authorName} per qualche minuto, a scopo di assistenza, e aprirai la schermata da cui ha segnalato il problema. L'operazione viene registrata nell'audit log.`}
              </Text>
              <View style={styles.rowActions}>
                <Pressable style={styles.secondaryButton} onPress={() => setPending(null)}>
                  <Text style={styles.secondaryButtonLabel}>Annulla</Text>
                </Pressable>
                <Pressable
                  style={[styles.button, impersonating && local.disabled]}
                  disabled={impersonating}
                  onPress={() => void confirmImpersonation()}
                  testID="feedback-admin-impersonate-confirm"
                >
                  <Text style={styles.buttonLabel}>{impersonating ? "Accesso…" : "Conferma"}</Text>
                </Pressable>
              </View>
            </View>
          ) : null}
        </View>
      </Modal>
    </PageContainer>
  );
}

const local = lazyStyles(() =>
  StyleSheet.create({
    count: { color: colors.foreground, fontWeight: typography.fontWeight.semibold },
    filters: { flexDirection: "row", flexWrap: "wrap", gap: spacing.sm },
    chip: {
      minHeight: 40,
      paddingHorizontal: spacing.md,
      justifyContent: "center",
      borderRadius: radius.pill,
      borderWidth: 1,
      borderColor: colors.border,
    },
    chipSelected: { backgroundColor: colors.brand, borderColor: colors.brand },
    chipLabel: { color: colors.foreground },
    chipLabelSelected: { color: colors.onBrand, fontWeight: typography.fontWeight.semibold },
    status: {
      alignSelf: "flex-start",
      overflow: "hidden",
      paddingHorizontal: spacing.sm,
      paddingVertical: 2,
      borderRadius: radius.pill,
      backgroundColor: colors.accentMuted,
      color: colors.foreground,
      fontSize: typography.fontSize.sm,
      fontWeight: typography.fontWeight.semibold,
    },
    message: { color: colors.foreground, fontSize: typography.fontSize.md },
    image: { width: "100%", height: 220, borderRadius: radius.md, backgroundColor: colors.background },
    videoButton: {
      minHeight: 48,
      justifyContent: "center",
      paddingHorizontal: spacing.md,
      borderRadius: radius.md,
      borderWidth: 1,
      borderColor: colors.border,
    },
    videoLabel: { color: colors.accent, fontWeight: typography.fontWeight.semibold },
    noteInput: { minHeight: 64 },
    primary: {
      minHeight: 44,
      padding: spacing.sm,
      borderRadius: radius.pill,
      backgroundColor: colors.brand,
      alignItems: "center",
      justifyContent: "center",
    },
    primaryLabel: { color: colors.onBrand, fontWeight: typography.fontWeight.semibold },
    secondary: {
      minHeight: 44,
      padding: spacing.sm,
      borderWidth: 1,
      borderColor: colors.border,
      borderRadius: radius.pill,
      alignItems: "center",
      justifyContent: "center",
    },
    secondaryLabel: { color: colors.accent, fontWeight: typography.fontWeight.semibold },
    disabled: { opacity: 0.5 },
    pager: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", gap: spacing.sm },
  }),
);
