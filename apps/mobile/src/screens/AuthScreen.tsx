import { lazyStyles } from "../theme/lazyStyles";
import { theme } from "@fantappero/ui/theme";
import { useNavigation } from "@react-navigation/core";
import type { NativeStackNavigationProp } from "@react-navigation/native-stack";
import { useEffect, useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { AppTextInput as TextInput } from "../components/AppTextInput";
import { useGoogleAuth } from "../auth/useGoogleAuth";
import { BrandLogo } from "../components/BrandLogo";
import { UiStatePanel } from "../components/UiStatePanel";
import { PageContainer } from "../layout/PageContainer";
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
    <View style={styles.root} testID="screen-auth">
      <PageContainer title="Accedi" testID="screen-auth-form">
        <View style={styles.brand}>
          <BrandLogo variant="full" size="lg" />
        </View>
        {remembered ? (
          <View style={styles.hero} testID="auth-welcome">
            <View style={styles.avatarRing}>
              <View style={styles.avatarInner}>
                <Text style={styles.avatarText}>{initialsOf(remembered.displayName)}</Text>
              </View>
            </View>
            <Text style={styles.heroTitle}>Bentornato, {firstName}</Text>
          </View>
        ) : (
          <Text style={styles.lead}>Accedi con il tuo account FantApperò.</Text>
        )}
        {error ? (
          <UiStatePanel
            state="error"
            title="Accesso non riuscito"
            message={error}
            testID="auth-error"
          />
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
              placeholder="tu@email.it"
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
          placeholder="Password"
          placeholderTextColor={colors.foregroundMuted}
          style={styles.input}
          accessibilityLabel="Password"
          testID="auth-password"
        />
        <Pressable
          accessibilityRole="button"
          accessibilityLabel="Password dimenticata"
          onPress={() => navigation.navigate("AuthForgotPassword")}
          style={styles.linkRow}
          testID="auth-forgot-link"
        >
          <Text style={styles.link}>Password dimenticata?</Text>
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
            style={[styles.secondaryButton, googleSubmitting && styles.disabled]}
            testID="auth-google-submit"
          >
            <Text style={styles.secondaryLabel}>
              {googleSubmitting ? "Accesso…" : "Continua con Google"}
            </Text>
          </Pressable>
        ) : null}
        {remembered ? (
          <Pressable accessibilityRole="button" accessibilityLabel={`Non sei ${firstName}? Cambia account`} onPress={switchAccount} style={styles.linkRow} testID="auth-not-you">
            <Text style={styles.link}>Non sei {firstName}? Cambia account</Text>
          </Pressable>
        ) : null}
        <Pressable
          accessibilityRole="button"
          accessibilityLabel="Registrati"
          onPress={() => navigation.navigate("AuthRegister")}
          style={styles.linkRow}
          testID="auth-register-link"
        >
          <Text style={styles.muted}>
            Non hai un account? <Text style={styles.link}>Registrati</Text>
          </Text>
        </Pressable>
      </PageContainer>
    </View>
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
    minHeight: 44,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.md,
    paddingHorizontal: spacing.md,
    color: colors.foreground,
    backgroundColor: colors.backgroundElevated,
  },
  primaryButton: {
    marginTop: spacing.lg,
    minHeight: 44,
    paddingVertical: spacing.md,
    borderRadius: radius.pill,
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
    width: 92,
    height: 92,
    borderRadius: 46,
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
