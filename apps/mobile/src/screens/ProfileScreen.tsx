import {
  DELETE_ACCOUNT_CONFIRMATION_PHRASE,
  PROFILE_LANGUAGE_OPTIONS,
  PROFILE_TIMEZONE_OPTIONS,
  type UserProfile,
} from "@fantappero/contracts";
import { theme } from "@fantappero/ui/theme";
import * as ImagePicker from "expo-image-picker";
import { useCallback, useState } from "react";
import { Image, Pressable, Share, StyleSheet, Switch, Text, TextInput, View } from "react-native";
import { deleteAccount, exportAccountData } from "../api/privacy";
import {
  fetchProfile,
  recordPolicyConsent,
  removeAvatar,
  updateInviteAvailability,
  updateProfile,
  uploadAvatar,
} from "../api/profile";
import { UiStatePanel } from "../components/UiStatePanel";
import { useScreenData } from "../hooks/useScreenData";
import { PageContainer } from "../layout/PageContainer";
import { getApiErrorMessage, useAuthSession } from "../session/DemoSessionContext";
import { resolveAvatarUrl } from "../utils/avatar";

const { colors, spacing, typography, radius } = theme;

function parseQuietHour(value: string): number | null | undefined {
  const trimmed = value.trim();
  if (trimmed === "") {
    return null;
  }
  if (!/^\d+$/.test(trimmed)) {
    return undefined;
  }
  const parsed = Number(trimmed);
  if (parsed < 0 || parsed > 23) {
    return undefined;
  }
  return parsed;
}

/** Profilo utente — preferenze e privacy via API (EP02-02). */
export function ProfileScreen() {
  const { accessToken, logout, updateDisplayName } = useAuthSession();
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [displayName, setDisplayName] = useState("");
  const [timezone, setTimezone] = useState("Europe/Rome");
  const [notificationsEmail, setNotificationsEmail] = useState(true);
  const [notificationsPush, setNotificationsPush] = useState(true);
  const [quietHoursStartHour, setQuietHoursStartHour] = useState("");
  const [quietHoursEndHour, setQuietHoursEndHour] = useState("");
  const [availableForInvites, setAvailableForInvites] = useState(false);
  const [policyAccepted, setPolicyAccepted] = useState(false);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [avatarBusy, setAvatarBusy] = useState(false);
  const [deletePhrase, setDeletePhrase] = useState("");
  const [deletePassword, setDeletePassword] = useState("");

  const applyProfile = useCallback((next: UserProfile) => {
    setProfile(next);
    setDisplayName(next.displayName);
    setTimezone(next.timezone);
    setNotificationsEmail(next.notificationsEmail);
    setNotificationsPush(next.notificationsPush);
    setQuietHoursStartHour(next.quietHoursStartHour?.toString() ?? "");
    setQuietHoursEndHour(next.quietHoursEndHour?.toString() ?? "");
    setAvailableForInvites(next.availableForInvites);
    setPolicyAccepted(next.policyVersion === next.currentPolicyVersion);
  }, []);

  const loadProfile = useCallback(
    async (options?: { silent?: boolean }) => {
      if (!accessToken) {
        setLoadError("Sessione non disponibile. Accedi di nuovo.");
        setLoading(false);
        return;
      }
      if (!options?.silent) {
        setLoading(true);
      }
      setLoadError(null);
      try {
        applyProfile(await fetchProfile(accessToken));
      } catch (error) {
        setLoadError(getApiErrorMessage(error, "Impossibile caricare il profilo."));
      } finally {
        setLoading(false);
      }
    },
    [accessToken, applyProfile],
  );

  const { refreshing, onRefresh } = useScreenData(loadProfile);

  async function handleSave() {
    setFormError(null);
    setSuccessMessage(null);
    if (!displayName.trim()) {
      setFormError("Inserisci un nome visualizzato.");
      return;
    }
    if (!accessToken || !profile) {
      setFormError("Sessione non disponibile. Accedi di nuovo.");
      return;
    }
    if ((quietHoursStartHour.trim() === "") !== (quietHoursEndHour.trim() === "")) {
      setFormError("Imposta sia l'inizio sia la fine del silenzio, oppure lasciali entrambi vuoti.");
      return;
    }
    const parsedStartHour = parseQuietHour(quietHoursStartHour);
    const parsedEndHour = parseQuietHour(quietHoursEndHour);
    if (parsedStartHour === undefined || parsedEndHour === undefined) {
      setFormError("Le ore di silenzio devono essere comprese tra 0 e 23.");
      return;
    }
    setSaving(true);
    try {
      const updated = await updateProfile(accessToken, {
        displayName: displayName.trim(),
        language: profile.language,
        timezone,
        notificationsEmail,
        notificationsPush,
        quietHoursStartHour: parsedStartHour,
        quietHoursEndHour: parsedEndHour,
      });
      applyProfile(updated);
      updateDisplayName(updated.displayName);
      setSuccessMessage("Preferenze salvate con successo.");
    } catch (error) {
      setFormError(getApiErrorMessage(error, "Salvataggio non riuscito."));
    } finally {
      setSaving(false);
    }
  }

  async function handlePickAvatar() {
    setFormError(null);
    setSuccessMessage(null);
    if (!accessToken) {
      setFormError("Sessione non disponibile. Accedi di nuovo.");
      return;
    }
    const permission = await ImagePicker.requestMediaLibraryPermissionsAsync();
    if (!permission.granted) {
      setFormError("Permesso di accesso alle foto negato.");
      return;
    }
    const result = await ImagePicker.launchImageLibraryAsync({
      mediaTypes: ["images"],
      quality: 0.8,
    });
    if (result.canceled || !result.assets?.[0]) {
      return;
    }
    const asset = result.assets[0];
    const name = asset.fileName ?? asset.uri.split("/").pop() ?? "avatar.jpg";
    const type = asset.mimeType ?? "image/jpeg";
    setAvatarBusy(true);
    try {
      const updated = await uploadAvatar(accessToken, { uri: asset.uri, name, type });
      applyProfile(updated);
      setSuccessMessage("Avatar aggiornato.");
    } catch (error) {
      setFormError(getApiErrorMessage(error, "Caricamento avatar non riuscito."));
    } finally {
      setAvatarBusy(false);
    }
  }

  async function handleRemoveAvatar() {
    setFormError(null);
    setSuccessMessage(null);
    if (!accessToken || !profile?.avatarUrl) {
      return;
    }
    setAvatarBusy(true);
    try {
      const updated = await removeAvatar(accessToken);
      applyProfile(updated);
      setSuccessMessage("Avatar rimosso.");
    } catch (error) {
      setFormError(getApiErrorMessage(error, "Rimozione avatar non riuscita."));
    } finally {
      setAvatarBusy(false);
    }
  }

  async function handlePolicyConsent() {
    setFormError(null);
    setSuccessMessage(null);
    if (!policyAccepted) {
      setFormError("Accetta la policy per continuare.");
      return;
    }
    if (!accessToken || !profile) {
      setFormError("Sessione non disponibile. Accedi di nuovo.");
      return;
    }
    setSaving(true);
    try {
      const updated = await recordPolicyConsent(accessToken, {
        policyVersion: profile.currentPolicyVersion,
        accepted: true,
      });
      applyProfile(updated);
      setSuccessMessage("Consenso alla policy registrato.");
    } catch (error) {
      setFormError(getApiErrorMessage(error, "Registrazione consenso non riuscita."));
    } finally {
      setSaving(false);
    }
  }

  async function handleInviteAvailabilityChange(next: boolean) {
    setFormError(null);
    setSuccessMessage(null);
    if (profile?.userType === "ai") {
      setFormError("Gli account IA sono sempre disponibili e non possono modificare questa preferenza.");
      return;
    }
    if (!accessToken) {
      setFormError("Sessione non disponibile. Accedi di nuovo.");
      return;
    }
    setSaving(true);
    try {
      const updated = await updateInviteAvailability(accessToken, next);
      applyProfile(updated);
      setSuccessMessage("Disponibilità agli inviti aggiornata.");
    } catch (error) {
      setFormError(getApiErrorMessage(error, "Aggiornamento disponibilità non riuscito."));
    } finally {
      setSaving(false);
    }
  }

  async function handleExportData() {
    setFormError(null);
    setSuccessMessage(null);
    if (!accessToken) {
      setFormError("Sessione non disponibile. Accedi di nuovo.");
      return;
    }
    setSaving(true);
    try {
      const payload = await exportAccountData(accessToken);
      await Share.share({
        message: JSON.stringify(payload, null, 2),
        title: `fantappero-export-${payload.exportedAt.slice(0, 10)}.json`,
      });
      setSuccessMessage("Esportazione completata. Condividi o salva il JSON.");
    } catch (error) {
      setFormError(getApiErrorMessage(error, "Esportazione non riuscita."));
    } finally {
      setSaving(false);
    }
  }

  async function handleDeleteAccount() {
    setFormError(null);
    setSuccessMessage(null);
    if (deletePhrase !== DELETE_ACCOUNT_CONFIRMATION_PHRASE) {
      setFormError(`Digita ${DELETE_ACCOUNT_CONFIRMATION_PHRASE} per confermare.`);
      return;
    }
    if (!deletePassword.trim()) {
      setFormError("Inserisci la password per eliminare l'account.");
      return;
    }
    if (!accessToken) {
      setFormError("Sessione non disponibile. Accedi di nuovo.");
      return;
    }
    setSaving(true);
    try {
      await deleteAccount(accessToken, {
        confirmPhrase: deletePhrase,
        password: deletePassword,
      });
      await logout();
    } catch (error) {
      setFormError(getApiErrorMessage(error, "Eliminazione non riuscita."));
      setSaving(false);
    }
  }

  if (loading) {
    return (
      <PageContainer
        title="Profilo"
        testID="screen-profile"
        refreshing={refreshing}
        onRefresh={onRefresh}
      >
        <UiStatePanel
          state="loading"
          title="Caricamento profilo"
          message="Recupero preferenze…"
          testID="profile-loading"
        />
      </PageContainer>
    );
  }

  if (loadError || !profile) {
    return (
      <PageContainer
        title="Profilo"
        testID="screen-profile"
        refreshing={refreshing}
        onRefresh={onRefresh}
      >
        <UiStatePanel
          state="error"
          title="Profilo non disponibile"
          message={loadError ?? "Profilo non trovato."}
          testID="profile-load-error"
        />
        <Pressable accessibilityRole="button" onPress={() => void loadProfile()} style={styles.secondaryButton}>
          <Text style={styles.secondaryButtonLabel}>Ricarica</Text>
        </Pressable>
      </PageContainer>
    );
  }

  return (
    <PageContainer
      title="Profilo"
      testID="screen-profile"
      refreshing={refreshing}
      onRefresh={onRefresh}
    >
      {successMessage ? (
        <UiStatePanel
          state="success"
          title="Operazione completata"
          message={successMessage}
          testID="profile-success"
        />
      ) : null}

      {formError ? (
        <UiStatePanel state="error" title="Errore" message={formError} testID="profile-error" />
      ) : null}

      <View style={styles.section} testID="profile-avatar-section">
        <Text style={styles.sectionTitle}>Avatar</Text>
        {resolveAvatarUrl(profile.avatarUrl) ? (
          <Image
            source={{ uri: resolveAvatarUrl(profile.avatarUrl) ?? undefined }}
            style={styles.avatarImage}
            testID="profile-avatar-image"
            accessibilityLabel="Avatar profilo"
          />
        ) : (
          <View style={styles.avatarPlaceholder} testID="profile-avatar-placeholder">
            <Text style={styles.avatarPlaceholderLabel}>
              {profile.displayName.charAt(0).toUpperCase()}
            </Text>
          </View>
        )}
        <Text style={styles.hint}>JPEG, PNG o WebP — massimo 2 MB.</Text>
        <Pressable
          accessibilityRole="button"
          disabled={avatarBusy}
          onPress={() => void handlePickAvatar()}
          style={[styles.secondaryButton, avatarBusy && styles.disabled]}
          testID="profile-avatar-pick"
        >
          <Text style={styles.secondaryButtonLabel}>
            {avatarBusy ? "Caricamento…" : "Cambia foto"}
          </Text>
        </Pressable>
        {profile.avatarUrl ? (
          <Pressable
            accessibilityRole="button"
            disabled={avatarBusy}
            onPress={() => void handleRemoveAvatar()}
            style={[styles.secondaryButton, avatarBusy && styles.disabled]}
            testID="profile-avatar-remove"
          >
            <Text style={styles.secondaryButtonLabel}>Rimuovi foto</Text>
          </Pressable>
        ) : null}
      </View>

      <View style={styles.section} testID="profile-form">
        <Text style={styles.label}>Nome visualizzato</Text>
        <TextInput
          value={displayName}
          onChangeText={setDisplayName}
          style={styles.input}
          accessibilityLabel="Nome visualizzato"
        />

        <Text style={styles.label}>Email</Text>
        <TextInput value={profile.email} editable={false} style={[styles.input, styles.readonly]} />

        <Text style={styles.label}>Lingua</Text>
        <Text style={styles.value}>{PROFILE_LANGUAGE_OPTIONS[0]?.label ?? "Italiano"}</Text>

        <Text style={styles.label}>Fuso orario</Text>
        <View style={styles.timezoneList}>
          {PROFILE_TIMEZONE_OPTIONS.map((option) => (
            <Pressable
              key={option.value}
              accessibilityRole="button"
              accessibilityState={{ selected: timezone === option.value }}
              onPress={() => setTimezone(option.value)}
              style={[styles.timezoneOption, timezone === option.value && styles.timezoneSelected]}
              testID={`profile-timezone-${option.value}`}
            >
              <Text style={styles.timezoneLabel}>{option.label}</Text>
            </Pressable>
          ))}
        </View>

        <View style={styles.switchRow}>
          <Text style={styles.label}>Notifiche email</Text>
          <Switch
            value={notificationsEmail}
            onValueChange={setNotificationsEmail}
            testID="profile-notifications-email"
          />
        </View>
        <View style={styles.switchRow}>
          <Text style={styles.label}>Notifiche push</Text>
          <Switch
            value={notificationsPush}
            onValueChange={setNotificationsPush}
            testID="profile-notifications-push"
          />
        </View>

        <Text style={styles.sectionTitle}>Silenzio notifiche (email/push)</Text>
        <Text style={styles.hint}>Ore 0-23. Lascia entrambi i campi vuoti per disattivare.</Text>
        <View style={styles.quietHoursRow}>
          <View style={styles.quietHoursField}>
            <Text style={styles.label}>Dalle ore</Text>
            <TextInput
              value={quietHoursStartHour}
              onChangeText={setQuietHoursStartHour}
              style={styles.input}
              keyboardType="number-pad"
              maxLength={2}
              accessibilityLabel="Silenzio notifiche dalle ore"
              testID="profile-quiet-hours-start"
            />
          </View>
          <View style={styles.quietHoursField}>
            <Text style={styles.label}>Alle ore</Text>
            <TextInput
              value={quietHoursEndHour}
              onChangeText={setQuietHoursEndHour}
              style={styles.input}
              keyboardType="number-pad"
              maxLength={2}
              accessibilityLabel="Silenzio notifiche alle ore"
              testID="profile-quiet-hours-end"
            />
          </View>
        </View>

        <Pressable
          accessibilityRole="button"
          disabled={saving}
          onPress={() => void handleSave()}
          style={[styles.primaryButton, saving && styles.disabled]}
          testID="profile-save"
        >
          <Text style={styles.primaryButtonLabel}>
            {saving ? "Salvataggio…" : "Salva preferenze"}
          </Text>
        </Pressable>
      </View>

      <View style={styles.section} testID="profile-directory-availability-section">
        <Text style={styles.sectionTitle}>Directory fantallenatori</Text>
        <Text style={styles.hint}>
          Se attivo, gli amministratori di lega possono invitarti dalla directory.
        </Text>
        <View style={styles.switchRow}>
          <Text style={styles.label}>
            {availableForInvites ? "Disponibile per inviti" : "Non disponibile"}
          </Text>
          <Switch
            value={availableForInvites}
            disabled={saving || profile.userType === "ai"}
            onValueChange={(available) => void handleInviteAvailabilityChange(available)}
            testID="profile-directory-availability"
          />
        </View>
      </View>

      <View style={styles.section} testID="profile-policy-pending">
        <Text style={styles.sectionTitle}>Privacy</Text>
        <Text style={styles.hint}>
          Policy versione {profile.currentPolicyVersion}. Accetta per continuare.
        </Text>
        <View style={styles.switchRow}>
          <Text style={styles.label}>Accetto la policy</Text>
          <Switch
            value={policyAccepted}
            onValueChange={setPolicyAccepted}
            testID="profile-policy-checkbox"
          />
        </View>
        <Pressable
          accessibilityRole="button"
          disabled={saving}
          onPress={() => void handlePolicyConsent()}
          style={styles.secondaryButton}
          testID="profile-policy-submit"
        >
          <Text style={styles.secondaryButtonLabel}>Registra consenso</Text>
        </Pressable>
      </View>

      <View style={styles.section} testID="profile-privacy-actions">
        <Text style={styles.sectionTitle}>I tuoi dati</Text>
        <Text style={styles.hint}>Esporta o elimina l&apos;account.</Text>
        <Pressable
          accessibilityRole="button"
          disabled={saving}
          onPress={() => void handleExportData()}
          style={styles.secondaryButton}
          testID="profile-export-data"
        >
          <Text style={styles.secondaryButtonLabel}>Esporta i miei dati</Text>
        </Pressable>
        <Text style={styles.hint}>
          Per eliminare l&apos;account digita {DELETE_ACCOUNT_CONFIRMATION_PHRASE} e conferma con la
          password.
        </Text>
        <TextInput
          value={deletePhrase}
          onChangeText={setDeletePhrase}
          style={styles.input}
          autoCapitalize="characters"
          placeholder={DELETE_ACCOUNT_CONFIRMATION_PHRASE}
          placeholderTextColor={colors.foregroundMuted}
          testID="profile-delete-phrase"
        />
        <TextInput
          value={deletePassword}
          onChangeText={setDeletePassword}
          style={styles.input}
          secureTextEntry
          placeholder="Password"
          placeholderTextColor={colors.foregroundMuted}
          testID="profile-delete-password"
        />
        <Pressable
          accessibilityRole="button"
          disabled={saving}
          onPress={() => void handleDeleteAccount()}
          style={styles.dangerButton}
          testID="profile-delete-submit"
        >
          <Text style={styles.dangerButtonLabel}>Elimina il mio account</Text>
        </Pressable>
      </View>

      <View style={styles.section} testID="profile-session-actions">
        <Text style={styles.sectionTitle}>Sessione</Text>
        <Text style={styles.hint}>Termina la sessione corrente e torna alla schermata di accesso.</Text>
        <Pressable
          accessibilityRole="button"
          onPress={() => void logout()}
          style={styles.logoutButton}
          testID="profile-logout"
        >
          <Text style={styles.logoutButtonLabel}>Logout</Text>
        </Pressable>
      </View>
    </PageContainer>
  );
}

const styles = StyleSheet.create({
  section: {
    gap: spacing.sm,
    marginBottom: spacing.lg,
  },
  sectionTitle: {
    fontSize: typography.fontSize.lg,
    fontWeight: typography.fontWeight.semibold,
    color: colors.foreground,
  },
  label: {
    fontSize: typography.fontSize.sm,
    fontWeight: typography.fontWeight.medium,
    color: colors.foregroundMuted,
  },
  value: {
    fontSize: typography.fontSize.md,
    color: colors.foreground,
  },
  hint: {
    fontSize: typography.fontSize.sm,
    color: colors.foregroundMuted,
  },
  input: {
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.md,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    color: colors.foreground,
    backgroundColor: colors.backgroundElevated,
  },
  readonly: {
    opacity: 0.7,
  },
  avatarImage: {
    width: 88,
    height: 88,
    borderRadius: 44,
    backgroundColor: colors.backgroundElevated,
  },
  avatarPlaceholder: {
    width: 88,
    height: 88,
    borderRadius: 44,
    backgroundColor: colors.backgroundElevated,
    alignItems: "center",
    justifyContent: "center",
  },
  avatarPlaceholderLabel: {
    fontSize: typography.fontSize.lg,
    fontWeight: typography.fontWeight.semibold,
    color: colors.foreground,
  },
  quietHoursRow: {
    flexDirection: "row",
    gap: spacing.sm,
  },
  quietHoursField: {
    flex: 1,
    gap: spacing.xs,
  },
  timezoneList: {
    gap: spacing.xs,
  },
  timezoneOption: {
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.md,
    padding: spacing.sm,
  },
  timezoneSelected: {
    borderColor: colors.accent,
    backgroundColor: colors.backgroundElevated,
  },
  timezoneLabel: {
    color: colors.foreground,
    fontSize: typography.fontSize.sm,
  },
  switchRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    marginTop: spacing.sm,
  },
  primaryButton: {
    marginTop: spacing.md,
    backgroundColor: colors.accent,
    borderRadius: radius.md,
    paddingVertical: spacing.md,
    alignItems: "center",
  },
  primaryButtonLabel: {
    color: colors.accentContrast,
    fontWeight: typography.fontWeight.semibold,
  },
  secondaryButton: {
    marginTop: spacing.sm,
    borderWidth: 1,
    borderColor: colors.accent,
    borderRadius: radius.md,
    paddingVertical: spacing.md,
    alignItems: "center",
  },
  secondaryButtonLabel: {
    color: colors.accent,
    fontWeight: typography.fontWeight.semibold,
  },
  dangerButton: {
    marginTop: spacing.sm,
    borderWidth: 1,
    borderColor: colors.danger,
    borderRadius: radius.md,
    paddingVertical: spacing.md,
    alignItems: "center",
  },
  dangerButtonLabel: {
    color: colors.danger,
    fontWeight: typography.fontWeight.semibold,
  },
  logoutButton: {
    marginTop: spacing.sm,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.md,
    paddingVertical: spacing.md,
    alignItems: "center",
    backgroundColor: colors.backgroundElevated,
  },
  logoutButtonLabel: {
    color: colors.foreground,
    fontWeight: typography.fontWeight.semibold,
  },
  disabled: {
    opacity: 0.6,
  },
});
