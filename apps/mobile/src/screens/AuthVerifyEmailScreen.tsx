import { useNavigation, useRoute, type RouteProp } from "@react-navigation/core";
import type { NativeStackNavigationProp } from "@react-navigation/native-stack";
import { useState } from "react";
import { Pressable, Text, View } from "react-native";
import { AuthShell } from "../auth/AuthShell";
import { AppTextInput as TextInput } from "../components/AppTextInput";
import { verifyEmail } from "../api/auth";
import { UiStatePanel } from "../components/UiStatePanel";
import type { RootStackParamList } from "../navigation/types";
import { getApiErrorMessage } from "../session/DemoSessionContext";
import { authFormStyles as styles, authPageStyles } from "./AuthScreen";

/**
 * Verifica email — allineata a web /accedi/verifica. Il link dell'email apre questa
 * schermata con il codice già scritto (`navigation/deepLinks.ts`); resta possibile
 * incollarlo a mano, come in AuthResetPasswordScreen.
 */
export function AuthVerifyEmailScreen() {
  const navigation = useNavigation<NativeStackNavigationProp<RootStackParamList>>();
  // Freccia indietro: torna alla schermata precedente (di solito Accedi), anche da un link.
  const goBack = () => (navigation.canGoBack() ? navigation.goBack() : navigation.navigate("Auth"));
  const route = useRoute<RouteProp<RootStackParamList, "AuthVerifyEmail">>();
  const [token, setToken] = useState(route.params?.token ?? "");
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function onSubmit() {
    setError(null);
    if (!token.trim()) {
      setError("Inserisci il codice ricevuto via email, oppure apri il link completo.");
      return;
    }
    setSubmitting(true);
    try {
      const response = await verifyEmail({ token: token.trim() });
      setSuccessMessage(response.message);
    } catch (submitError) {
      setError(getApiErrorMessage(submitError, "Verifica email non riuscita."));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <AuthShell testID="screen-auth-verify-email" onBack={goBack}>
      <View style={authPageStyles.form} testID="screen-auth-verify-email-form">
        <Text style={styles.heroTitleLeft} accessibilityRole="header">
          Verifica email
        </Text>
        {successMessage ? (
          <>
            <UiStatePanel
              state="success"
              title="Email verificata"
              message={successMessage}
              testID="auth-verify-email-success"
            />
            <Pressable
              accessibilityRole="button"
              onPress={() => navigation.navigate("Auth")}
              style={styles.linkRow}
              testID="auth-verify-email-back-login"
            >
              <Text style={styles.link}>Accedi ora</Text>
            </Pressable>
          </>
        ) : (
          <>
            <Text style={styles.lead}>
              Incolla il codice di verifica ricevuto via email per completare la registrazione.
            </Text>
            {error ? (
              <UiStatePanel
                state="error"
                title="Verifica non riuscita"
                message={error}
                testID="auth-verify-email-error"
              />
            ) : null}
            <Text style={styles.label}>Codice di verifica</Text>
            <TextInput
              value={token}
              onChangeText={setToken}
              autoCapitalize="none"
              autoCorrect={false}
              placeholder="Incolla il codice"
              placeholderTextColor={styles.muted.color}
              style={styles.input}
              accessibilityLabel="Codice di verifica"
              testID="auth-verify-email-token"
            />
            <Pressable
              accessibilityRole="button"
              disabled={submitting}
              onPress={() => void onSubmit()}
              style={[styles.primaryButton, submitting && styles.disabled]}
              testID="auth-verify-email-submit"
            >
              <Text style={styles.primaryLabel}>
                {submitting ? "Verifica…" : "Verifica email"}
              </Text>
            </Pressable>
            <Pressable
              accessibilityRole="button"
              onPress={() => navigation.navigate("Auth")}
              style={styles.linkRow}
              testID="auth-verify-email-login-link"
            >
              <Text style={styles.link}>Torna al login</Text>
            </Pressable>
          </>
        )}
      </View>
    </AuthShell>
  );
}
