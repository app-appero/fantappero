import { lazyStyles } from "../theme/lazyStyles";
import { theme } from "@fantappero/ui/theme";
import { DISPLAY_FONT } from "../theme/fonts";
import { useNavigation } from "@react-navigation/core";
import type { NativeStackNavigationProp } from "@react-navigation/native-stack";
import { useEffect, useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { AppTextInput as TextInput } from "../components/AppTextInput";
import { useGoogleAuth } from "../auth/useGoogleAuth";
import { AuthShell } from "../auth/AuthShell";
import { UiStatePanel } from "../components/UiStatePanel";
import type { RootStackParamList } from "../navigation/types";
import { getApiErrorMessage, useAuthSession } from "../session/DemoSessionContext";
import { clearLastUser, initialsOf, readLastUser, writeLastUser, type LastUser } from "../session/lastUser";
import { getMemorySession } from "../session/sessionStorage";

const { colors, spacing, typography, radius } = theme;

/** Login — allineato a web /accedi. */
export function AuthScreen() {
  const navigation = useNavigation<NativeStackNavigationProp<RootStackParamList>>();
  const { login, loginWithGoogle } = useAuthSession();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [googleSubmitting, setGoogleSubmitting] = useState(false);
  const [remembered, setRemembered] = useState<LastUser | null>(null);
  useEffect(() => {
    void readLastUser().then((last) => {
      if (last) {
        setRemembered(last);
        setEmail(last.email);
      }
    });
  }, []);
  const firstName = remembered?.displayName.trim().split(/\s+/)[0] ?? "";

  function switchAccount() {
    setRemembered(null);
    setEmail("");
    setPassword("");
    setError(null);
    void clearLastUser();
  }
  const googleAuth = useGoogleAuth((idToken) => {
    setError(null);
    setGoogleSubmitting(true);
    return loginWithGoogle(idToken)
      .catch((googleError: unknown) => {
        setError(getApiErrorMessage(googleError, "Accesso con Google non riuscito."));
      })
      .finally(() => {
        setGoogleSubmitting(false);
      });
  });

  async function onLogin() {
    setError(null);
    if (!email.trim() || !password) {
      setError("Inserisci email e password.");
      return;
    }
    setSubmitting(true);
    try {
      await login(email.trim(), password);
      const user = getMemorySession()?.user;
      if (user?.displayName) {
        void writeLastUser({ displayName: user.displayName, email: email.trim() });
      }
    } catch (loginError) {
      setError(getApiErrorMessage(loginError, "Accesso non riuscito."));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <AuthShell
      testID="screen-auth"
      footer={
        <>
          {googleAuth.available ? (
            <Pressable
              accessibilityRole="button"
              accessibilityLabel="Continua con Google"
              disabled={googleSubmitting}
              onPress={() => {
                void googleAuth.promptAsync().catch((googleError: unknown) => {
                  setError(getApiErrorMessage(googleError, "Accesso con Google non riuscito."));
                });
              }}
              style={[styles.googleButton, googleSubmitting && styles.disabled]}
              testID="auth-google-submit"
            >
              <View style={styles.googleMark}>
                <Text style={styles.googleMarkLabel}>G</Text>
              </View>
              <Text style={styles.secondaryLabel}>{googleSubmitting ? "Accesso…" : "Continua con Google"}</Text>
            </Pressable>
          ) : null}
          <Pressable
            accessibilityRole="button"
            accessibilityLabel="Crea un account"
            onPress={() => navigation.navigate("AuthRegister")}
            style={styles.centerLink}
            testID="auth-register-link"
          >
            <Text style={styles.muted}>
              Nuovo qui? <Text style={styles.linkStrong}>Crea un account</Text>
            </Text>
          </Pressable>
        </>
      }
    >
      <View testID="screen-auth-form">
        {remembered ? (
          <View style={styles.hero} testID="auth-welcome">
            <View style={styles.avatarRing}>
              <View style={styles.avatarInner}>
                <Text style={styles.avatarText}>{initialsOf(remembered.displayName)}</Text>
              </View>
            </View>
            <Text style={styles.displayTitle}>Bentornato, {firstName}</Text>
          </View>
        ) : (
          <Text style={styles.displayTitleLeft}>
            Il fantacalcio{"\n"}che si <Text style={styles.displayAccent}>gioca{"\n"}</Text>
            <Text style={styles.displayAccent2}>davvero</Text>
          </Text>
        )}
        {error ? (
          <UiStatePanel state="error" title="Accesso non riuscito" message={error} testID="auth-error" />
        ) : null}
        {remembered ? (
          <View style={styles.accountRow} testID="auth-account">
            <View style={styles.accountText}>
              <Text style={styles.accountCaption}>Account</Text>
              <Text style={styles.accountEmail} numberOfLines={1}>{remembered.email}</Text>
            </View>
            <Pressable accessibilityRole="button" accessibilityLabel="Cambia account" onPress={switchAccount} testID="auth-switch-account">
              <Text style={styles.link}>Cambia</Text>
            </Pressable>
          </View>
        ) : (
          <>
            <Text style={styles.label}>Email</Text>
            <TextInput
              value={email}
              onChangeText={setEmail}
              autoCapitalize="none"
              autoCorrect={false}
              keyboardType="email-address"
              placeholder="nome@esempio.it"
              placeholderTextColor={colors.foregroundMuted}
              style={styles.input}
              accessibilityLabel="Email"
              testID="auth-email"
            />
          </>
        )}
        <Text style={styles.label}>Password</Text>
        <TextInput
          value={password}
          onChangeText={setPassword}
          secureTextEntry
          placeholder="La tua password"
          placeholderTextColor={colors.foregroundMuted}
          style={styles.input}
          accessibilityLabel="Password"
          testID="auth-password"
        />
        <Pressable
          accessibilityRole="button"
          accessibilityLabel="Password dimenticata"
          onPress={() => navigation.navigate("AuthForgotPassword")}
          style={styles.rightLink}
          testID="auth-forgot-link"
        >
          <Text style={styles.linkUnderline}>Password dimenticata?</Text>
        </Pressable>
        <Pressable
          accessibilityRole="button"
          accessibilityLabel="Accedi"
          disabled={submitting}
          onPress={() => void onLogin()}
          style={[styles.primaryButton, submitting && styles.disabled]}
          testID="auth-login-submit"
        >
          <Text style={styles.primaryLabel}>{submitting ? "Accesso…" : remembered ? `Accedi come ${firstName}` : "Accedi"}</Text>
        </Pressable>
        {remembered ? (
          <Pressable accessibilityRole="button" accessibilityLabel={`Non sei ${firstName}? Cambia account`} onPress={switchAccount} style={styles.centerLink} testID="auth-not-you">
            <Text style={styles.linkUnderline}>Non sei {firstName}? Cambia account</Text>
          </Pressable>
        ) : null}
      </View>
    </AuthShell>
  );
}

export const authFormStyles = lazyStyles(() => StyleSheet.create({
  root: {
    flex: 1,
    backgroundColor: colors.background,
  },
  brand: {
    marginBottom: spacing.md,
  },
  lead: {
    color: colors.foregroundMuted,
    fontSize: typography.fontSize.sm,
    marginBottom: spacing.md,
  },
  label: {
    marginTop: spacing.sm,
    color: colors.foregroundMuted,
    fontSize: typography.fontSize.sm,
    fontWeight: typography.fontWeight.semibold,
  },
  input: {
    marginTop: spacing.xs,
    minHeight: 54,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 18,
    paddingHorizontal: spacing.md + 2,
    color: colors.foreground,
    backgroundColor: colors.background,
  },
  primaryButton: {
    marginTop: spacing.md,
    minHeight: 58,
    paddingVertical: spacing.md,
    borderRadius: 20,
    backgroundColor: colors.brand,
    alignItems: "center",
    justifyContent: "center",
  },
  primaryLabel: {
    color: colors.onBrand,
    fontWeight: typography.fontWeight.semibold,
    fontSize: typography.fontSize.md,
  },
  secondaryButton: {
    marginTop: spacing.sm,
    minHeight: 44,
    paddingVertical: spacing.md,
    borderRadius: radius.pill,
    borderWidth: 1,
    borderColor: colors.border,
    alignItems: "center",
    justifyContent: "center",
  },
  secondaryLabel: {
    color: colors.foreground,
    fontWeight: typography.fontWeight.semibold,
    fontSize: typography.fontSize.md,
  },
  linkRow: {
    marginTop: spacing.md,
    minHeight: 44,
    justifyContent: "center",
  },
  link: {
    color: colors.accent,
    fontWeight: typography.fontWeight.semibold,
    fontSize: typography.fontSize.sm,
  },
  muted: {
    color: colors.foregroundMuted,
    fontSize: typography.fontSize.sm,
  },
  disabled: {
    opacity: 0.6,
  },
  hero: {
    alignItems: "center",
    gap: spacing.sm,
    marginBottom: spacing.md,
  },
  avatarRing: {
    width: 100,
    height: 100,
    borderRadius: 50,
    padding: 4,
    backgroundColor: colors.accentSecondary,
  },
  avatarInner: {
    flex: 1,
    borderRadius: 42,
    backgroundColor: colors.brand,
    alignItems: "center",
    justifyContent: "center",
  },
  avatarText: {
    color: colors.onBrand,
    fontSize: 30,
    fontStyle: "italic",
    fontWeight: "800",
  },
  heroTitle: {
    color: colors.foreground,
    fontSize: typography.fontSize.xl,
    fontStyle: "italic",
    fontWeight: "800",
    textTransform: "uppercase",
    textAlign: "center",
  },
  displayTitle: {
    color: colors.foreground,
    fontSize: 40,
    lineHeight: 42,
    fontFamily: DISPLAY_FONT,
    textTransform: "uppercase",
    textAlign: "center",
  },
  displayTitleLeft: {
    color: colors.foreground,
    fontSize: 46,
    lineHeight: 48,
    fontFamily: DISPLAY_FONT,
    textTransform: "uppercase",
    marginBottom: spacing.md,
  },
  displayAccent: { color: "#8CA8FF" },
  displayAccent2: { color: "#C58CFF" },
  googleButton: {
    minHeight: 54,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: spacing.sm,
    borderRadius: 20,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.backgroundElevated,
  },
  googleMark: { width: 24, height: 24, borderRadius: 12, backgroundColor: "#fff", alignItems: "center", justifyContent: "center" },
  googleMarkLabel: { color: "#4285F4", fontWeight: "800", fontSize: 14 },
  centerLink: { minHeight: 40, alignItems: "center", justifyContent: "center" },
  rightLink: { alignSelf: "flex-end", minHeight: 40, justifyContent: "center" },
  linkUnderline: { color: colors.accent, fontSize: typography.fontSize.sm, textDecorationLine: "underline" },
  linkStrong: { color: colors.accent, fontWeight: typography.fontWeight.semibold, textDecorationLine: "underline" },
  stepBadge: {
    paddingHorizontal: spacing.md,
    paddingVertical: 6,
    borderRadius: radius.pill,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.backgroundElevated,
  },
  stepBadgeLabel: { color: colors.foregroundMuted, fontSize: 12, fontWeight: "600" },
  orRow: { flexDirection: "row", alignItems: "center", gap: spacing.sm },
  orLine: { flex: 1, height: 1, backgroundColor: colors.border },
  heroTitleLeft: {
    color: colors.foreground,
    fontSize: typography.fontSize.xl,
    fontStyle: "italic",
    fontWeight: "800",
    textTransform: "uppercase",
    marginBottom: spacing.xs,
  },
  accountRow: {
    marginTop: spacing.sm,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: spacing.md,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.backgroundElevated,
  },
  accountText: {
    flex: 1,
    minWidth: 0,
  },
  accountCaption: {
    color: colors.foregroundMuted,
    fontSize: 11,
    letterSpacing: 1.4,
    textTransform: "uppercase",
  },
  accountEmail: {
    color: colors.foreground,
    fontWeight: typography.fontWeight.semibold,
  },
}));

const styles = authFormStyles;
