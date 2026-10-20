import { useNavigation } from "@react-navigation/core";
import type { NativeStackNavigationProp } from "@react-navigation/native-stack";
import { useState } from "react";
import Ionicons from "@expo/vector-icons/Ionicons";
import { Pressable, Text, View } from "react-native";
import { AppTextInput as TextInput } from "../components/AppTextInput";
import { register as registerApi } from "../api/auth";
import { AuthShell } from "../auth/AuthShell";
import { useGoogleAuth } from "../auth/useGoogleAuth";
import { UiStatePanel } from "../components/UiStatePanel";
import type { RootStackParamList } from "../navigation/types";
import { getApiErrorMessage, useAuthSession } from "../session/DemoSessionContext";
import { authFormStyles as styles } from "./AuthScreen";

/** Registrazione — allineata a web /accedi/registrati. */
export function AuthRegisterScreen() {
  const navigation = useNavigation<NativeStackNavigationProp<RootStackParamList>>();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const { loginWithGoogle } = useAuthSession();
  const [googleSubmitting, setGoogleSubmitting] = useState(false);
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

  async function onSubmit() {
    setError(null);
    if (!email.trim() || !password || !displayName.trim()) {
      setError("Compila tutti i campi obbligatori.");
      return;
    }
    if (password !== confirmPassword) {
      setError("Le password non coincidono.");
      return;
    }
    setSubmitting(true);
    try {
      const response = await registerApi({
        email: email.trim(),
        password,
        displayName: displayName.trim(),
      });
      setSuccessMessage(response.message);
    } catch (submitError) {
      setError(getApiErrorMessage(submitError, "Registrazione non riuscita."));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <AuthShell
      testID="screen-auth-register"
      badge={
        successMessage ? undefined : (
          <View style={styles.stepBadge}>
            <Text style={styles.stepBadgeLabel}>Passo 1 di 3</Text>
          </View>
        )
      }
      footer={
        successMessage ? undefined : (
          <>
            {googleAuth.available ? (
              <Pressable
                accessibilityRole="button"
                accessibilityLabel="Registrati con Google"
                disabled={googleSubmitting}
                onPress={() => {
                  void googleAuth.promptAsync().catch((googleError: unknown) => {
                    setError(getApiErrorMessage(googleError, "Accesso con Google non riuscito."));
                  });
                }}
                style={[styles.googleMain, googleSubmitting && styles.disabled]}
                testID="auth-register-google"
              >
                <View style={styles.googleMarkMain}>
                  <Text style={styles.googleMarkLabel}>G</Text>
                </View>
                <Text style={styles.googleMainLabel}>{googleSubmitting ? "Accesso…" : "Registrati con Google"}</Text>
              </Pressable>
            ) : null}
            <View style={styles.appleDisabled} accessibilityRole="button" accessibilityState={{ disabled: true }} accessibilityLabel="Registrati con Apple, disponibile presto" testID="auth-register-apple-disabled">
              <Ionicons name="logo-apple" size={22} color="#FFFFFF" />
              <Text style={styles.appleLabel}>Registrati con Apple</Text>
              <View style={styles.soonChip}>
                <Text style={styles.soonLabel}>PRESTO</Text>
              </View>
            </View>
            <View style={styles.orRow}>
              <View style={styles.orLine} />
              <Text style={styles.muted}>oppure con email</Text>
              <View style={styles.orLine} />
            </View>
            <Text style={styles.label}>Nome visualizzato</Text>
            <TextInput
              value={displayName}
              onChangeText={setDisplayName}
              placeholder="Es. Marco Rossi"
              placeholderTextColor={styles.muted.color}
              style={styles.input}
              accessibilityLabel="Nome visualizzato"
              testID="auth-register-display-name"
            />
            <Text style={styles.label}>Email</Text>
            <TextInput
              value={email}
              onChangeText={setEmail}
              autoCapitalize="none"
              autoCorrect={false}
              keyboardType="email-address"
              placeholder="nome@esempio.it"
              placeholderTextColor={styles.muted.color}
              style={styles.input}
              accessibilityLabel="Email"
              testID="auth-register-email"
            />
            <Text style={styles.label}>Password</Text>
            <TextInput
              value={password}
              onChangeText={setPassword}
              secureTextEntry
              placeholder="Almeno 8 caratteri"
              placeholderTextColor={styles.muted.color}
              style={styles.input}
              accessibilityLabel="Password"
              testID="auth-register-password"
            />
            <Text style={styles.label}>Conferma password</Text>
            <TextInput
              value={confirmPassword}
              onChangeText={setConfirmPassword}
              secureTextEntry
              placeholder="Ripeti la password"
              placeholderTextColor={styles.muted.color}
              style={styles.input}
              accessibilityLabel="Conferma password"
              testID="auth-register-confirm-password"
            />
            <Pressable
              accessibilityRole="button"
              disabled={submitting}
              onPress={() => void onSubmit()}
              style={[styles.emailButton, { marginTop: 8 }, submitting && styles.disabled]}
              testID="auth-register-submit"
            >
              <Text style={styles.emailButtonLabel}>{submitting ? "Registrazione…" : "Crea account con email"}</Text>
            </Pressable>
            <Pressable
              accessibilityRole="button"
              onPress={() => navigation.navigate("Auth")}
              style={styles.centerLink}
              testID="auth-register-login-link"
            >
              <Text style={styles.muted}>
                Hai già un account? <Text style={styles.linkStrong}>Accedi</Text>
              </Text>
            </Pressable>
          </>
        )
      }
    >
      <View testID="screen-auth-register-form">
        {successMessage ? (
          <>
            <UiStatePanel
              state="success"
              title="Controlla la tua email"
              message={successMessage}
              testID="auth-register-success"
            />
            <Pressable
              accessibilityRole="button"
              onPress={() => navigation.navigate("AuthVerifyEmail")}
              style={styles.centerLink}
              testID="auth-register-verify-link"
            >
              <Text style={styles.linkUnderline}>Ho un codice di verifica</Text>
            </Pressable>
            <Pressable
              accessibilityRole="button"
              onPress={() => navigation.navigate("Auth")}
              style={styles.centerLink}
              testID="auth-register-back-login"
            >
              <Text style={styles.linkUnderline}>Torna al login</Text>
            </Pressable>
          </>
        ) : (
          <>
            <Text style={styles.displayTitleLeft}>
              Crea la tua{"\n"}
              <Text style={styles.displayAccent}>squadra</Text>
            </Text>
            {error ? (
              <UiStatePanel
                state="error"
                title="Registrazione non riuscita"
                message={error}
                testID="auth-register-error"
              />
            ) : null}
          </>
        )}
      </View>
    </AuthShell>
  );
}
