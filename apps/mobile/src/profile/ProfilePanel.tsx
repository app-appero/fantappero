import { useEffect, useState } from "react";

import {

  ActivityIndicator,

  Image,

  Pressable,

  StyleSheet,

  Text,

  TextInput,

  View,

} from "react-native";

import {

  LANGUAGE_LABELS,

  PROFILE_POLICY_VERSION,

  SUPPORTED_LANGUAGES,

  type AsyncState,

  type SupportedLanguage,

  type UserProfileResponse,

  ui,

} from "@fantappero/contracts";

import { colors, spacing, typography } from "@fantappero/ui";

import { AuthApiError, type AuthClient } from "../api/auth";



function resolveLocale(language: string): SupportedLanguage {

  if (SUPPORTED_LANGUAGES.includes(language as SupportedLanguage)) {

    return language as SupportedLanguage;

  }

  return "it";

}



export interface ProfilePanelProps {

  client: AuthClient;

  token: string;

  profile: UserProfileResponse;

  onUpdated: (profile: UserProfileResponse) => void;

}



export function ProfilePanel({ client, token, profile, onUpdated }: ProfilePanelProps) {

  const copy = ui(resolveLocale(profile.language));

  const [status, setStatus] = useState<AsyncState>("idle");

  const [error, setError] = useState<string | null>(null);

  const [message, setMessage] = useState<string | null>(null);

  const [displayName, setDisplayName] = useState(profile.display_name ?? "");

  const [language, setLanguage] = useState(profile.language);

  const [timezone, setTimezone] = useState(profile.timezone);

  const [notificationsEmail, setNotificationsEmail] = useState(profile.notifications.email);

  const [notificationsPush, setNotificationsPush] = useState(profile.notifications.push);

  const [acceptPolicy, setAcceptPolicy] = useState(false);



  useEffect(() => {

    setDisplayName(profile.display_name ?? "");

    setLanguage(profile.language);

    setTimezone(profile.timezone);

    setNotificationsEmail(profile.notifications.email);

    setNotificationsPush(profile.notifications.push);

  }, [profile]);



  async function handleSave() {

    const payload: Record<string, unknown> = {};

    const trimmedName = displayName.trim();

    if (trimmedName !== (profile.display_name ?? "")) {

      if (!trimmedName) {

        setStatus("empty");

        setError(null);

        setMessage(null);

        return;

      }

      payload.display_name = trimmedName;

    }

    if (language !== profile.language) {

      payload.language = language;

    }

    if (timezone.trim() !== profile.timezone) {

      if (!timezone.trim()) {

        setStatus("empty");

        return;

      }

      payload.timezone = timezone.trim();

    }

    if (notificationsEmail !== profile.notifications.email) {

      payload.notifications_email = notificationsEmail;

    }

    if (notificationsPush !== profile.notifications.push) {

      payload.notifications_push = notificationsPush;

    }

    if (acceptPolicy && !profile.policy_consent_at) {

      payload.accept_policy = true;

      payload.policy_version = PROFILE_POLICY_VERSION;

    }



    if (Object.keys(payload).length === 0) {

      setStatus("empty");

      setError(null);

      setMessage(null);

      return;

    }



    setStatus("loading");

    setError(null);

    try {

      const updated = await client.updateProfile(token, payload);

      onUpdated(updated);

      setAcceptPolicy(false);

      setStatus("success");

      setMessage(copy.profileSaved);

    } catch (caught) {

      setStatus("error");

      if (caught instanceof AuthApiError) {

        setError(caught.message);

      } else {

        setError(copy.networkError);

      }

    }

  }



  return (

    <View testID="profile-panel">

      {status === "loading" ? (

        <ActivityIndicator color={colors.ok} testID="profile-loading" />

      ) : null}

      {status === "empty" ? (

        <Text style={styles.muted} testID="profile-empty">

          {copy.profileEmptyChange}

        </Text>

      ) : null}

      {status === "error" && error ? (

        <Text style={styles.error} testID="profile-error">

          {error}

        </Text>

      ) : null}

      {status === "success" && message ? (

        <Text style={styles.success} testID="profile-success">

          {message}

        </Text>

      ) : null}



      {profile.avatar_url ? (

        <Image

          source={{ uri: profile.avatar_url }}

          style={styles.avatar}

          testID="profile-avatar"

        />

      ) : (

        <Text style={styles.muted} testID="profile-avatar-empty">

          {copy.noAvatar}

        </Text>

      )}



      <TextInput

        testID="profile-display-name"

        value={displayName}

        onChangeText={setDisplayName}

        placeholder={copy.displayName}

        placeholderTextColor={colors.muted}

        style={styles.input}

      />



      <Text style={styles.label}>

        {copy.language}: {LANGUAGE_LABELS[resolveLocale(language)]}

      </Text>

      <View style={styles.languageRow}>

        {SUPPORTED_LANGUAGES.map((code) => (

          <Pressable key={code} onPress={() => setLanguage(code)} testID={`profile-lang-${code}`}>

            <Text style={code === language ? styles.langActive : styles.lang}>

              {LANGUAGE_LABELS[code]}

            </Text>

          </Pressable>

        ))}

      </View>



      <TextInput

        testID="profile-timezone"

        value={timezone}

        onChangeText={setTimezone}

        placeholder={copy.timezone}

        placeholderTextColor={colors.muted}

        style={styles.input}

      />



      <Pressable

        onPress={() => setNotificationsEmail((value) => !value)}

        testID="profile-notifications-email"

      >

        <Text style={styles.value}>

          {copy.emailNotifications}: {notificationsEmail ? copy.on : copy.off}

        </Text>

      </Pressable>



      <Pressable

        onPress={() => setNotificationsPush((value) => !value)}

        testID="profile-notifications-push"

      >

        <Text style={styles.value}>

          {copy.pushNotifications}: {notificationsPush ? copy.on : copy.off}

        </Text>

      </Pressable>



      {profile.policy_consent_at ? (

        <Text style={styles.muted} testID="profile-policy-accepted">

          {copy.policyAccepted} ({profile.policy_version})

        </Text>

      ) : (

        <Pressable onPress={() => setAcceptPolicy((value) => !value)} testID="profile-accept-policy">

          <Text style={styles.value}>

            {copy.acceptPolicyShort}

            {PROFILE_POLICY_VERSION}: {acceptPolicy ? copy.yes : copy.no}

          </Text>

        </Pressable>

      )}



      <Pressable style={styles.button} onPress={() => void handleSave()} testID="profile-save">

        <Text style={styles.buttonLabel}>{copy.saveProfile}</Text>

      </Pressable>

    </View>

  );

}



const styles = StyleSheet.create({

  muted: {

    color: colors.muted,

    marginBottom: spacing.sm,

  },

  error: {

    color: "#f87171",

    marginBottom: spacing.sm,

  },

  success: {

    color: colors.ok,

    marginBottom: spacing.sm,

  },

  label: {

    color: colors.muted,

    fontSize: typography.fontSize.sm,

    marginTop: spacing.sm,

  },

  value: {

    color: colors.foreground,

    fontSize: typography.fontSize.md,

    marginTop: spacing.sm,

  },

  input: {

    borderWidth: 1,

    borderColor: colors.muted,

    borderRadius: 8,

    padding: spacing.sm,

    color: colors.foreground,

    marginBottom: spacing.sm,

    marginTop: spacing.sm,

  },

  avatar: {

    width: 64,

    height: 64,

    borderRadius: 32,

    marginBottom: spacing.sm,

  },

  languageRow: {

    flexDirection: "row",

    flexWrap: "wrap",

    gap: spacing.sm,

    marginBottom: spacing.sm,

  },

  lang: {

    color: colors.muted,

    marginRight: spacing.sm,

  },

  langActive: {

    color: colors.ok,

    fontWeight: "600",

    marginRight: spacing.sm,

  },

  button: {

    backgroundColor: colors.ok,

    borderRadius: 8,

    padding: spacing.sm,

    alignItems: "center",

    marginTop: spacing.md,

  },

  buttonLabel: {

    color: colors.background,

    fontWeight: "600",

  },

});


