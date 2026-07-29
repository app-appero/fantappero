import { useMemo, useState } from "react";

import { ActivityIndicator, Pressable, StyleSheet, Text, TextInput, View } from "react-native";

import {

  DEFAULT_UI_LOCALE,

  SUPPORTED_LANGUAGES,

  type AsyncState,

  type AuthView,

  type SupportedLanguage,

  type UserProfileResponse,

  ui,

} from "@fantappero/contracts";

import { colors, spacing, typography } from "@fantappero/ui";

import { AuthApiError, createAuthClient, type AuthClient } from "../api/auth";
import { createLeagueClient, type LeagueClient } from "../api/leagues";
import { getMobileApiBaseUrl } from "../config/env";
import { CreateLeaguePanel } from "../leagues/CreateLeaguePanel";
import { ProfilePanel } from "../profile/ProfilePanel";

import { PrivacyPanel } from "../profile/PrivacyPanel";



function resolveLocale(language?: string): SupportedLanguage {

  if (language && SUPPORTED_LANGUAGES.includes(language as SupportedLanguage)) {

    return language as SupportedLanguage;

  }

  return DEFAULT_UI_LOCALE;

}



export interface AuthScreenProps {

  client?: AuthClient;

  leagueClient?: LeagueClient;

  initialView?: AuthView;

}



export function AuthScreen({

  client: clientOverride,

  leagueClient: leagueClientOverride,

  initialView = "login",

}: AuthScreenProps) {

  const client = useMemo(

    () => clientOverride ?? createAuthClient(getMobileApiBaseUrl()),

    [clientOverride],

  );

  const leagueClient = useMemo(

    () => leagueClientOverride ?? createLeagueClient(getMobileApiBaseUrl()),

    [leagueClientOverride],

  );



  const [view, setView] = useState<AuthView>(initialView);

  const [status, setStatus] = useState<AsyncState>("idle");

  const [error, setError] = useState<string | null>(null);

  const [message, setMessage] = useState<string | null>(null);

  const [email, setEmail] = useState("");

  const [password, setPassword] = useState("");

  const [user, setUser] = useState<UserProfileResponse | null>(null);

  const [token, setToken] = useState<string | null>(null);



  const copy = ui(resolveLocale(user?.language));



  async function handleSubmit() {

    if (!email.trim() || !password.trim()) {

      setStatus("empty");

      setError(null);

      setMessage(null);

      return;

    }



    setStatus("loading");

    setError(null);

    try {

      const session =

        view === "register"

          ? await client.register(email.trim(), password)

          : await client.login(email.trim(), password);

      const profile = await client.me(session.access_token);

      setToken(session.access_token);

      setUser(profile);

      setView("account");

      setStatus("success");

      const strings = ui(resolveLocale(profile.language));

      setMessage(view === "register" ? strings.accountCreated : strings.welcomeBack);

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

    <View style={styles.container} testID="auth-screen">

      <Text style={styles.brand}>FantApperò</Text>

      <Text style={styles.title}>

        {view === "profile"

          ? copy.profileTitle

          : view === "privacy"

            ? copy.privacyTitle

            : view === "create-league"

              ? copy.createLeagueTitle

            : view === "account"

              ? copy.accountTitle

              : copy.signInTitle}

      </Text>



      {status === "loading" ? (

        <ActivityIndicator color={colors.ok} testID="auth-loading" />

      ) : null}

      {status === "empty" ? (

        <Text style={styles.muted} testID="auth-empty">

          {copy.fillEmailPassword}

        </Text>

      ) : null}

      {status === "error" && error ? (

        <Text style={styles.error} testID="auth-error">

          {error}

        </Text>

      ) : null}

      {status === "success" && message ? (

        <Text style={styles.success} testID="auth-success">

          {message}

        </Text>

      ) : null}



      {view === "account" && user ? (

        <View testID="account-panel">

          <Text style={styles.label}>{copy.email}</Text>

          <Text style={styles.value} testID="account-email">

            {user.email}

          </Text>

          <Text style={styles.label}>{copy.name}</Text>

          <Text style={styles.value} testID="account-display-name">

            {user.display_name ?? "—"}

          </Text>

          <Text style={styles.label}>{copy.verified}</Text>

          <Text style={styles.value} testID="account-verified">

            {user.email_verified ? copy.yes : copy.no}

          </Text>

          {!user.email_verified ? (
            <Text style={styles.warning} testID="account-verify-required">
              {copy.emailNotVerified}
            </Text>
          ) : null}

          <Pressable

            style={styles.button}

            onPress={() => setView("profile")}

            testID="account-edit-profile"

          >

            <Text style={styles.buttonLabel}>{copy.editProfile}</Text>

          </Pressable>

          {!user.email_verified ? (
            <Pressable
              style={styles.button}
              onPress={() => setView("verify-email")}
              testID="account-verify-email"
            >
              <Text style={styles.buttonLabel}>{copy.goVerifyEmail}</Text>
            </Pressable>
          ) : null}

          <Pressable

            style={[styles.button, !user.email_verified ? styles.buttonDisabled : null]}

            onPress={() => setView("create-league")}

            testID="account-create-league"

            disabled={!user.email_verified}

          >

            <Text style={styles.buttonLabel}>{copy.createLeagueLink}</Text>

          </Pressable>

          <Pressable

            style={styles.button}

            onPress={() => setView("privacy")}

            testID="account-privacy"

          >

            <Text style={styles.buttonLabel}>{copy.privacyAndData}</Text>

          </Pressable>

        </View>

      ) : null}



      {view === "privacy" && token ? (

        <PrivacyPanel

          client={client}

          token={token}

          onDeleted={() => {

            setToken(null);

            setUser(null);

            setView("login");

            setStatus("success");

            setMessage(copy.accountDeleted);

          }}

        />

      ) : null}



      {view === "create-league" && token ? (

        <CreateLeaguePanel

          client={leagueClient}

          token={token}

          locale={resolveLocale(user?.language)}

          emailVerified={user?.email_verified ?? false}

          onVerifyEmail={() => setView("verify-email")}

          onCreated={() => setView("account")}

        />

      ) : null}



      {view === "profile" && user && token ? (

        <ProfilePanel

          client={client}

          token={token}

          profile={user}

          onUpdated={(updated) => setUser(updated)}

        />

      ) : null}



      {view === "login" || view === "register" ? (

        <View>

          <TextInput

            testID="auth-email"

            value={email}

            onChangeText={setEmail}

            placeholder={copy.email}

            placeholderTextColor={colors.muted}

            autoCapitalize="none"

            keyboardType="email-address"

            style={styles.input}

          />

          <TextInput

            testID="auth-password"

            value={password}

            onChangeText={setPassword}

            placeholder={copy.password}

            placeholderTextColor={colors.muted}

            secureTextEntry

            style={styles.input}

          />

          <Pressable style={styles.button} onPress={() => void handleSubmit()} testID="auth-submit">

            <Text style={styles.buttonLabel}>

              {view === "register" ? copy.register : copy.signIn}

            </Text>

          </Pressable>

          <Pressable onPress={() => setView(view === "login" ? "register" : "login")}>

            <Text style={styles.link}>

              {view === "login" ? copy.createAccountLink : copy.backToSignIn}

            </Text>

          </Pressable>

        </View>

      ) : null}

    </View>

  );

}



const styles = StyleSheet.create({

  container: {

    flex: 1,

    backgroundColor: colors.background,

    padding: spacing.xl,

    justifyContent: "center",

  },

  brand: {

    color: colors.muted,

    letterSpacing: 1.2,

    textTransform: "uppercase",

    fontSize: typography.fontSize.sm,

    marginBottom: spacing.sm,

  },

  title: {

    color: colors.foreground,

    fontSize: typography.fontSize.xl,

    marginBottom: spacing.md,

  },

  muted: {

    color: colors.muted,

    marginBottom: spacing.sm,

  },

  error: {

    color: "#f87171",

    marginBottom: spacing.sm,

  },

  warning: {

    color: "#fbbf24",

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

  },

  input: {

    borderWidth: 1,

    borderColor: colors.muted,

    borderRadius: 8,

    padding: spacing.sm,

    color: colors.foreground,

    marginBottom: spacing.sm,

  },

  button: {

    backgroundColor: colors.ok,

    borderRadius: 8,

    padding: spacing.sm,

    alignItems: "center",

    marginTop: spacing.sm,

  },

  buttonDisabled: {

    backgroundColor: colors.muted,

  },

  buttonLabel: {

    color: colors.background,

    fontWeight: "600",

  },

  link: {

    color: colors.muted,

    marginTop: spacing.md,

    textAlign: "center",

  },

});


