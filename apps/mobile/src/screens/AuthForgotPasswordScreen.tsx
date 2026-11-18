import { useNavigation } from "@react-navigation/core";
import type { NativeStackNavigationProp } from "@react-navigation/native-stack";
import { useState } from "react";
import { Pressable, Text, View } from "react-native";
import { AuthShell } from "../auth/AuthShell";
import { AppTextInput as TextInput } from "../components/AppTextInput";
import { forgotPassword } from "../api/auth";
import { UiStatePanel } from "../components/UiStatePanel";
import type { RootStackParamList } from "../navigation/types";
import { getApiErrorMessage } from "../session/DemoSessionContext";
import { authFormStyles as styles, authPageStyles } from "./AuthScreen";

/** Recupero password — allineato a web /accedi/recupera. */
export function AuthForgotPasswordScreen() {
  const navigation = useNavigation<NativeStackNavigationProp<RootStackParamList>>();
  // Freccia indietro: torna alla schermata precedente (di solito Accedi), anche da un link.
  const goBack = () => (navigation.canGoBack() ? navigation.goBack() : navigation.navigate("Auth"));
  const [email, setEmail] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function onSubmit() {
    setError(null);
    if (!email.trim()) {
      setError("Inserisci la tua email.");
      return;
    }
    setSubmitting(true);
    try {
      const response = await forgotPassword({ email: email.trim() });
      setSuccessMessage(response.message);
    } catch (submitError) {
      setError(getApiErrorMessage(submitError, "Richiesta non riuscita."));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <AuthShell testID="screen-auth-forgot" onBack={goBack}>
      <View style={authPageStyles.form} testID="screen-auth-forgot-form">
        <Text style={styles.heroTitleLeft} accessibilityRole="header">
          Recupera accesso
        </Text>
        {successMessage ? (
          <>
            <UiStatePanel
              state="success"
              title="Controlla la tua email"
              message={successMessage}
              testID="auth-forgot-success"
            />
            <Pressable
              accessibilityRole="button"
              onPress={() => navigation.navigate("Auth")}
              style={styles.linkRow}
              testID="auth-forgot-back-login"
            >
              <Text style={styles.link}>Torna al login</Text>
            </Pressable>
            <Pressable
              accessibilityRole="button"
              onPress={() => navigation.navigate("AuthResetPassword")}
              style={styles.linkRow}
              testID="auth-forgot-reset-link"
            >
              <Text style={styles.muted}>
                Hai già il codice? <Text style={styles.link}>Reimposta password</Text>
              </Text>
            </Pressable>
          </>
        ) : (
          <>
            <Text style={styles.lead}>
              Inserisci l&apos;email dell&apos;account: ti invieremo un link per reimpostare la
              password.
            </Text>
            {error ? (
              <UiStatePanel
                state="error"
                title="Richiesta non riuscita"
                message={error}
                testID="auth-forgot-error"
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
              placeholderTextColor={styles.muted.color}
              style={styles.input}
              accessibilityLabel="Email"
              testID="auth-forgot-email"
            />
            <Pressable
              accessibilityRole="button"
              disabled={submitting}
              onPress={() => void onSubmit()}
              style={[styles.primaryButton, submitting && styles.disabled]}
              testID="auth-forgot-submit"
            >
              <Text style={styles.primaryLabel}>
                {submitting ? "Invio…" : "Invia link di reset"}
              </Text>
            </Pressable>
            <Pressable
              accessibilityRole="button"
              onPress={() => navigation.navigate("Auth")}
              style={styles.linkRow}
              testID="auth-forgot-login-link"
            >
              <Text style={styles.link}>Torna al login</Text>
            </Pressable>
          </>
        )}
      </View>
    </AuthShell>
  );
}
