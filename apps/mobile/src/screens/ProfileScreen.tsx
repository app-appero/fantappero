import {
  DELETE_ACCOUNT_CONFIRMATION_PHRASE,
  PROFILE_LANGUAGE_OPTIONS,
  PROFILE_TIMEZONE_OPTIONS,
  type UserProfile,
} from "@fantappero/contracts";
import { useNavigation } from "@react-navigation/core";
import type { NativeStackNavigationProp } from "@react-navigation/native-stack";
import { theme } from "@fantappero/ui/theme";
import { useMemo, useState } from "react";
import { Pressable, StyleSheet, Switch, Text, TextInput, View } from "react-native";
import { PageContainer } from "../layout/PageContainer";
import type { RootStackParamList } from "../navigation/types";
import { UiStatePanel } from "../components/UiStatePanel";
import { useDemoSession } from "../session/DemoSessionContext";

const { colors, spacing, typography, radius } = theme;

const DEMO_PROFILE: UserProfile = {
  email: "demo@fantappero.local",
  displayName: "Marco Rossi",
  avatarUrl: null,
  language: "it",
  timezone: "Europe/Rome",
  notificationsEmail: true,
  notificationsPush: true,
  policyConsentAt: null,
  policyVersion: null,
  currentPolicyVersion: "2026-01",
  userType: "human",
  availableForInvites: false,
};

/** Profilo utente — preferenze in modalità demo (EP02-02). */
export function ProfileScreen() {
  const { user, logout, directoryAvailable, setDirectoryAvailable } = useDemoSession();
  const navigation = useNavigation<NativeStackNavigationProp<RootStackParamList>>();
  const initialProfile = useMemo(
    () => ({ ...DEMO_PROFILE, displayName: user.displayName }),
    [user.displayName],
  );

  const [displayName, setDisplayName] = useState(initialProfile.displayName);
  const [timezone, setTimezone] = useState(initialProfile.timezone);
  const [notificationsEmail, setNotificationsEmail] = useState(initialProfile.notificationsEmail);
  const [notificationsPush, setNotificationsPush] = useState(initialProfile.notificationsPush);
  const [policyAccepted, setPolicyAccepted] = useState(false);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [formError, setFormError] = useState<string | null>(null);

  function handleSave() {
    setFormError(null);
    if (!displayName.trim()) {
      setFormError("Inserisci un nome visualizzato.");
      return;
    }
    setSuccessMessage("Preferenze salvate (demo).");
  }

  function handlePolicyConsent() {
    if (!policyAccepted) {
      setFormError("Accetta la policy per continuare.");
      return;
    }
    setFormError(null);
    setSuccessMessage("Consenso registrato (demo).");
  }

  function handleLogout() {
    logout();
    setFormError(null);
    setSuccessMessage(null);
    navigation.navigate("Auth");
  }

  return (
    <PageContainer title="Profilo" testID="screen-profile">
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

      <View style={styles.section} testID="profile-form">
        <Text style={styles.label}>Nome visualizzato</Text>
        <TextInput
          value={displayName}
          onChangeText={setDisplayName}
          style={styles.input}
          accessibilityLabel="Nome visualizzato"
        />

        <Text style={styles.label}>Email</Text>
        <TextInput value={initialProfile.email} editable={false} style={[styles.input, styles.readonly]} />

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

        <Pressable
          accessibilityRole="button"
          onPress={handleSave}
          style={styles.primaryButton}
          testID="profile-save"
        >
          <Text style={styles.primaryButtonLabel}>Salva preferenze</Text>
        </Pressable>
      </View>

      <View style={styles.section} testID="profile-directory-availability-section">
        <Text style={styles.sectionTitle}>Directory fantallenatori</Text>
        <Text style={styles.hint}>
          Scegli manualmente se comparire nella directory demo. Il valore resta solo nella sessione
          locale e non viene pubblicato.
        </Text>
        <View style={styles.switchRow}>
          <Text style={styles.label}>
            {directoryAvailable ? "Disponibile per inviti" : "Non disponibile"}
          </Text>
          <Switch
            value={directoryAvailable}
            onValueChange={(available) => {
              setDirectoryAvailable(available);
              setSuccessMessage(
                available
                  ? "Disponibilità directory attivata (demo)."
                  : "Disponibilità directory disattivata (demo).",
              );
            }}
            testID="profile-directory-availability"
          />
        </View>
      </View>

      <View style={styles.section} testID="profile-policy-pending">
        <Text style={styles.sectionTitle}>Privacy</Text>
        <Text style={styles.hint}>
          Policy versione {initialProfile.currentPolicyVersion}. Accetta per continuare.
        </Text>
        <View style={styles.switchRow}>
          <Text style={styles.label}>Accetto la policy</Text>
          <Switch value={policyAccepted} onValueChange={setPolicyAccepted} testID="profile-policy-checkbox" />
        </View>
        <Pressable
          accessibilityRole="button"
          onPress={handlePolicyConsent}
          style={styles.secondaryButton}
          testID="profile-policy-submit"
        >
          <Text style={styles.secondaryButtonLabel}>Registra consenso</Text>
        </Pressable>
      </View>

      <View style={styles.section} testID="profile-privacy-actions">
        <Text style={styles.sectionTitle}>I tuoi dati</Text>
        <Text style={styles.hint}>
          Esporta o elimina l&apos;account. In modalità demo le azioni sono simulate.
        </Text>
        <Pressable
          accessibilityRole="button"
          onPress={() => setSuccessMessage("Esportazione simulata (demo).")}
          style={styles.secondaryButton}
          testID="profile-export-data"
        >
          <Text style={styles.secondaryButtonLabel}>Esporta i miei dati</Text>
        </Pressable>
        <Text style={styles.hint}>
          Per eliminare l&apos;account digita {DELETE_ACCOUNT_CONFIRMATION_PHRASE} e conferma con la
          password (demo).
        </Text>
        <Pressable
          accessibilityRole="button"
          onPress={() => setSuccessMessage("Eliminazione simulata (demo).")}
          style={styles.dangerButton}
          testID="profile-delete-submit"
        >
          <Text style={styles.dangerButtonLabel}>Elimina il mio account</Text>
        </Pressable>
      </View>

      <View style={styles.section} testID="profile-session-actions">
        <Text style={styles.sectionTitle}>Sessione</Text>
        <Text style={styles.hint}>Termina la sessione demo corrente e torna alla schermata di accesso.</Text>
        <Pressable
          accessibilityRole="button"
          onPress={handleLogout}
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
    color: colors.background,
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
});
