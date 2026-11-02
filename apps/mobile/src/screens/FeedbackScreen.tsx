import {
  FEEDBACK_CATEGORIES,
  FEEDBACK_CATEGORY_LABEL,
  FEEDBACK_MAX_ATTACHMENTS,
  FEEDBACK_MESSAGE_MAX_CHARS,
  FEEDBACK_MESSAGE_MIN_CHARS,
  FEEDBACK_STATUS_LABEL,
  feedbackAttachmentKind,
  validateFeedbackDraft,
  type FeedbackCategory,
  type FeedbackReportSummary,
} from "@fantappero/contracts";
import { theme } from "@fantappero/ui/theme";
import * as ImagePicker from "expo-image-picker";
import { useCallback, useState } from "react";
import { Image, Pressable, StyleSheet, Text, View } from "react-native";
import { fetchMyFeedback, sendFeedback } from "../api/feedback";
import { AppTextInput as TextInput } from "../components/AppTextInput";
import { UiStatePanel } from "../components/UiStatePanel";
import { readLastScreen } from "../feedback/lastScreen";
import { toPickedAttachment, type PickedAttachment } from "../feedback/pickedAsset";
import { useScreenData } from "../hooks/useScreenData";
import { PageContainer } from "../layout/PageContainer";
import { getApiErrorMessage, useAuthSession } from "../session/DemoSessionContext";
import { lazyStyles } from "../theme/lazyStyles";

const { colors, spacing, typography, radius } = theme;

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

function formatSize(bytes: number | null | undefined): string {
  if (bytes == null) {
    return "";
  }
  return bytes >= 1024 * 1024
    ? ` · ${(bytes / (1024 * 1024)).toFixed(1)} MB`
    : ` · ${Math.max(1, Math.round(bytes / 1024))} KB`;
}

/** «Segnala un problema»: testo + screenshot o video, per aiutare gli operatori a trovare i bug. */
export function FeedbackScreen() {
  const { accessToken } = useAuthSession();
  const [category, setCategory] = useState<FeedbackCategory>("bug");
  const [message, setMessage] = useState("");
  const [picked, setPicked] = useState<PickedAttachment[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [sent, setSent] = useState(false);
  const [sending, setSending] = useState(false);
  const [mine, setMine] = useState<FeedbackReportSummary[]>([]);
  const [mineError, setMineError] = useState<string | null>(null);

  const loadMine = useCallback(async () => {
    if (!accessToken) {
      return;
    }
    try {
      setMine(await fetchMyFeedback(accessToken));
      setMineError(null);
    } catch (loadError) {
      setMineError(getApiErrorMessage(loadError, "Impossibile caricare le tue segnalazioni."));
    }
  }, [accessToken]);

  const { refreshing, onRefresh } = useScreenData(loadMine);

  async function onPick() {
    setSent(false);
    const remaining = FEEDBACK_MAX_ATTACHMENTS - picked.length;
    if (remaining <= 0) {
      setError(`Puoi allegare al massimo ${FEEDBACK_MAX_ATTACHMENTS} file.`);
      return;
    }
    const permission = await ImagePicker.requestMediaLibraryPermissionsAsync();
    if (!permission.granted) {
      setError("Permesso di accesso alla galleria negato. Abilitalo dalle impostazioni del telefono.");
      return;
    }
    const result = await ImagePicker.launchImageLibraryAsync({
      mediaTypes: ["images", "videos"],
      allowsMultipleSelection: true,
      selectionLimit: remaining,
      quality: 0.8,
      // Su iOS `compatible` converte HEIC in JPEG, che il server accetta.
      preferredAssetRepresentationMode: ImagePicker.UIImagePickerPreferredAssetRepresentationMode.Compatible,
    });
    if (result.canceled || !result.assets?.length) {
      return;
    }
    const next = [
      ...picked,
      ...result.assets.map((asset, index) => toPickedAttachment(asset, picked.length + index)),
    ];
    const problem = validateFeedbackDraft({
      message: "x".repeat(FEEDBACK_MESSAGE_MIN_CHARS),
      attachments: next,
    });
    if (problem) {
      setError(problem);
      return;
    }
    setError(null);
    setPicked(next);
  }

  async function onSubmit() {
    setSent(false);
    const problem = validateFeedbackDraft({ message, attachments: picked });
    if (problem) {
      setError(problem);
      return;
    }
    if (!accessToken) {
      setError("Sessione non disponibile. Accedi di nuovo.");
      return;
    }
    setError(null);
    setSending(true);
    try {
      await sendFeedback(accessToken, {
        message,
        category,
        pageContext: readLastScreen(),
        files: picked.map((item) => ({ uri: item.uri, name: item.name, type: item.mimeType ?? undefined })),
      });
      setPicked([]);
      setMessage("");
      setSent(true);
      void loadMine();
    } catch (submitError) {
      setError(getApiErrorMessage(submitError, "Invio non riuscito. Riprova tra poco."));
    } finally {
      setSending(false);
    }
  }

  const hasVideo = picked.some((item) => feedbackAttachmentKind(item.mimeType) === "video");
  return (
    <PageContainer
      title="Segnala un problema"
      testID="screen-feedback"
      refreshing={refreshing}
      onRefresh={onRefresh}
    >
      <Text style={styles.body}>
        Hai trovato un bug o hai un'idea? Raccontacelo: ci aiuta a sistemare l'app. Se puoi, aggiungi
        uno screenshot o un breve video che mostra il problema.
      </Text>

      <Text style={styles.label}>Di cosa si tratta?</Text>
      <View style={styles.row}>
        {FEEDBACK_CATEGORIES.map((value) => (
          <Pressable
            key={value}
            accessibilityRole="button"
            accessibilityState={{ selected: category === value }}
            onPress={() => setCategory(value)}
            style={[styles.chip, category === value && styles.chipSelected]}
            testID={`feedback-category-${value}`}
          >
            <Text style={[styles.chipLabel, category === value && styles.chipLabelSelected]}>
              {FEEDBACK_CATEGORY_LABEL[value]}
            </Text>
          </Pressable>
        ))}
      </View>

      <Text style={styles.label}>Cosa è successo?</Text>
      <TextInput
        value={message}
        onChangeText={(value) => {
          setMessage(value);
          setSent(false);
        }}
        multiline
        textAlignVertical="top"
        maxLength={FEEDBACK_MESSAGE_MAX_CHARS}
        placeholder="Cosa stavi facendo, cosa ti aspettavi e cosa è successo invece."
        style={[styles.input, styles.multiline]}
        accessibilityLabel="Descrizione del problema"
        testID="feedback-message"
      />
      <Text style={styles.hint}>
        {message.trim().length}/{FEEDBACK_MESSAGE_MAX_CHARS} caratteri (almeno {FEEDBACK_MESSAGE_MIN_CHARS})
      </Text>

      <Text style={styles.label}>Immagine o video (facoltativo)</Text>
      <Pressable
        accessibilityRole="button"
        onPress={() => void onPick()}
        disabled={sending || picked.length >= FEEDBACK_MAX_ATTACHMENTS}
        style={[
          styles.secondaryButton,
          (sending || picked.length >= FEEDBACK_MAX_ATTACHMENTS) && styles.disabled,
        ]}
        testID="feedback-add-file"
      >
        <Text style={styles.secondaryLabel}>Aggiungi immagine o video</Text>
      </Pressable>
      <Text style={styles.hint}>
        Fino a {FEEDBACK_MAX_ATTACHMENTS} file: immagini fino a 8 MB, video fino a 50 MB.
      </Text>
      {picked.map((item, index) => {
        const isVideo = feedbackAttachmentKind(item.mimeType) === "video";
        return (
          <View key={`${item.uri}-${index}`} style={styles.fileRow} testID="feedback-file">
            {isVideo ? (
              <View style={[styles.thumb, styles.thumbVideo]}>
                <Text style={styles.thumbGlyph}>▶</Text>
              </View>
            ) : (
              <Image source={{ uri: item.uri }} style={styles.thumb} />
            )}
            <View style={styles.fileText}>
              <Text style={styles.fileName} numberOfLines={1}>
                {item.name}
              </Text>
              <Text style={styles.hint}>
                {isVideo ? "Video" : "Immagine"}
                {formatSize(item.sizeBytes)}
              </Text>
            </View>
            <Pressable
              accessibilityRole="button"
              accessibilityLabel={`Rimuovi ${item.name}`}
              onPress={() => setPicked((current) => current.filter((_, i) => i !== index))}
              style={styles.removeButton}
            >
              <Text style={styles.removeLabel}>Rimuovi</Text>
            </Pressable>
          </View>
        );
      })}

      {error ? (
        <UiStatePanel state="error" title="Segnalazione non inviata" message={error} testID="feedback-error" />
      ) : null}
      {sent ? (
        <UiStatePanel
          state="success"
          title="Grazie, segnalazione inviata"
          message="Gli operatori l'hanno ricevuta. Qui sotto vedi lo stato di lavorazione."
          testID="feedback-sent"
        />
      ) : null}

      <Pressable
        accessibilityRole="button"
        onPress={() => void onSubmit()}
        disabled={sending}
        style={[styles.primaryButton, sending && styles.disabled]}
        testID="feedback-submit"
      >
        <Text style={styles.primaryLabel}>
          {sending ? (hasVideo ? "Caricamento del video…" : "Invio…") : "Invia segnalazione"}
        </Text>
      </Pressable>

      <Text style={styles.heading}>Le tue segnalazioni</Text>
      {mineError ? (
        <UiStatePanel state="error" title="Elenco non disponibile" message={mineError} testID="feedback-mine-error" />
      ) : mine.length === 0 ? (
        <Text style={styles.hint} testID="feedback-mine-empty">
          Non hai ancora inviato segnalazioni.
        </Text>
      ) : (
        <View testID="feedback-mine">
          {mine.map((report) => (
            <View key={report.id} style={styles.reportRow}>
              <Text style={[styles.status, styles[`status_${report.status}` as const]]}>
                {FEEDBACK_STATUS_LABEL[report.status]}
              </Text>
              <Text style={styles.reportTitle}>{FEEDBACK_CATEGORY_LABEL[report.category]}</Text>
              <Text style={styles.body}>{report.message}</Text>
              <Text style={styles.hint}>
                {formatDate(report.createdAt)}
                {report.attachmentCount > 0
                  ? ` · ${report.attachmentCount} allegat${report.attachmentCount === 1 ? "o" : "i"}`
                  : ""}
              </Text>
            </View>
          ))}
        </View>
      )}
    </PageContainer>
  );
}

const styles = lazyStyles(() =>
  StyleSheet.create({
    body: { color: colors.foreground, fontSize: typography.fontSize.md },
    heading: {
      marginTop: spacing.lg,
      color: colors.foreground,
      fontSize: typography.fontSize.lg,
      fontWeight: typography.fontWeight.semibold,
    },
    label: {
      marginTop: spacing.md,
      color: colors.foregroundMuted,
      fontSize: typography.fontSize.sm,
      fontWeight: typography.fontWeight.semibold,
    },
    hint: { color: colors.foregroundMuted, fontSize: typography.fontSize.sm },
    row: { flexDirection: "row", flexWrap: "wrap", gap: spacing.sm },
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
    input: {
      minHeight: 44,
      borderWidth: 1,
      borderColor: colors.border,
      borderRadius: radius.md,
      paddingHorizontal: spacing.md,
      paddingVertical: spacing.sm,
      color: colors.foreground,
      backgroundColor: colors.backgroundElevated,
    },
    multiline: { minHeight: 140 },
    primaryButton: {
      marginTop: spacing.md,
      minHeight: 48,
      padding: spacing.md,
      borderRadius: radius.pill,
      backgroundColor: colors.brand,
      alignItems: "center",
      justifyContent: "center",
    },
    primaryLabel: { color: colors.onBrand, fontWeight: typography.fontWeight.semibold },
    secondaryButton: {
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
    fileRow: {
      flexDirection: "row",
      alignItems: "center",
      gap: spacing.md,
      padding: spacing.sm,
      borderWidth: 1,
      borderColor: colors.border,
      borderRadius: radius.md,
    },
    thumb: { width: 56, height: 56, borderRadius: radius.md, backgroundColor: colors.backgroundElevated },
    thumbVideo: { alignItems: "center", justifyContent: "center" },
    thumbGlyph: { color: colors.foregroundMuted, fontSize: typography.fontSize.lg },
    fileText: { flex: 1, minWidth: 0 },
    fileName: { color: colors.foreground, fontWeight: typography.fontWeight.semibold },
    removeButton: { minHeight: 44, justifyContent: "center", paddingHorizontal: spacing.sm },
    removeLabel: { color: colors.danger, fontWeight: typography.fontWeight.semibold },
    reportRow: {
      marginTop: spacing.sm,
      padding: spacing.md,
      gap: 4,
      borderWidth: 1,
      borderColor: colors.border,
      borderRadius: radius.md,
    },
    reportTitle: { color: colors.foreground, fontWeight: typography.fontWeight.semibold },
    status: {
      alignSelf: "flex-start",
      overflow: "hidden",
      paddingHorizontal: spacing.sm,
      paddingVertical: 2,
      borderRadius: radius.pill,
      fontSize: typography.fontSize.sm,
      fontWeight: typography.fontWeight.semibold,
      color: colors.foreground,
    },
    status_new: { backgroundColor: colors.backgroundElevated },
    status_in_review: { backgroundColor: colors.warningMuted },
    status_resolved: { backgroundColor: colors.successMuted },
    status_dismissed: { backgroundColor: colors.backgroundElevated },
  }),
);
