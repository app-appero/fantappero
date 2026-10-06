import { theme } from "@fantappero/ui/theme";
import { useNavigation } from "@react-navigation/core";
import type { NativeStackNavigationProp } from "@react-navigation/native-stack";
import { useState } from "react";
import { Pressable, StyleSheet, Text, TextInput, View } from "react-native";
import { useGoogleAuth } from "../auth/useGoogleAuth";
import { BrandLogo } from "../components/BrandLogo";
import { UiStatePanel } from "../components/UiStatePanel";
import { PageContainer } from "../layout/PageContainer";
import type { RootStackParamList } from "../navigation/types";
import { getApiErrorMessage, useAuthSession } from "../session/DemoSessionContext";

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
  const googleAuth = useGoogleAuth((idToken) => {
    setError(null);
    setGoogleSubmitting(true);
    loginWithGoogle(idToken)
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
        <Text style={styles.lead}>Accedi con il tuo account FantApperò.</Text>
        {error ? (
          <UiStatePanel
            state="error"
            title="Accesso non riuscito"
            message={error}
            testID="auth-error"
          />
        ) : null}
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
          <Text style={styles.primaryLabel}>{submitting ? "Accesso…" : "Accedi"}</Text>
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

export const authFormStyles = StyleSheet.create({
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
    borderRadius: radius.md,
    backgroundColor: colors.accent,
    alignItems: "center",
    justifyContent: "center",
  },
  primaryLabel: {
    color: colors.accentContrast,
    fontWeight: typography.fontWeight.semibold,
    fontSize: typography.fontSize.md,
  },
  secondaryButton: {
    marginTop: spacing.sm,
    minHeight: 44,
    paddingVertical: spacing.md,
    borderRadius: radius.md,
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
});

const styles = authFormStyles;
