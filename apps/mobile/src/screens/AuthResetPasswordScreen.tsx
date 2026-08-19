import { useNavigation, useRoute, type RouteProp } from "@react-navigation/core";
import type { NativeStackNavigationProp } from "@react-navigation/native-stack";
import { useState } from "react";
import { Pressable, Text, TextInput, View } from "react-native";
import { resetPassword } from "../api/auth";
import { BrandLogo } from "../components/BrandLogo";
import { UiStatePanel } from "../components/UiStatePanel";
import { PageContainer } from "../layout/PageContainer";
import type { RootStackParamList } from "../navigation/types";
import { getApiErrorMessage } from "../session/DemoSessionContext";
import { authFormStyles as styles } from "./AuthScreen";

/** Reimposta password — allineata a web /accedi/reimposta-password. */
export function AuthResetPasswordScreen() {
  const navigation = useNavigation<NativeStackNavigationProp<RootStackParamList>>();
  const route = useRoute<RouteProp<RootStackParamList, "AuthResetPassword">>();
  const [token, setToken] = useState(route.params?.token ?? "");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function onSubmit() {
    setError(null);
    if (!token.trim()) {
      setError("Inserisci il token ricevuto via email, oppure apri il link completo.");
      return;
    }
    if (!password) {
      setError("Inserisci la nuova password.");
      return;
    }
    if (password !== confirmPassword) {
      setError("Le password non coincidono.");
      return;
    }
    setSubmitting(true);
    try {
      const response = await resetPassword({
        token: token.trim(),
        newPassword: password,
      });
      setSuccessMessage(response.message);
    } catch (submitError) {
      setError(getApiErrorMessage(submitError, "Reset password non riuscito."));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <View style={styles.root} testID="screen-auth-reset">
      <PageContainer title="Reimposta password" testID="screen-auth-reset-form">
        <View style={styles.brand}>
          <BrandLogo variant="full" size="lg" />
        </View>
        {successMessage ? (
          <>
            <UiStatePanel
              state="success"
              title="Password aggiornata"
              message={successMessage}
              testID="auth-reset-success"
            />
            <Pressable
              accessibilityRole="button"
              onPress={() => navigation.navigate("Auth")}
              style={styles.linkRow}
              testID="auth-reset-back-login"
            >
              <Text style={styles.link}>Vai al login</Text>
            </Pressable>
          </>
        ) : (
          <>
            <Text style={styles.lead}>Scegli una nuova password per il tuo account.</Text>
            {error ? (
              <UiStatePanel
                state="error"
                title="Reset non riuscito"
                message={error}
                testID="auth-reset-error"
              />
            ) : null}
            <Text style={styles.label}>Token dal link email</Text>
            <TextInput
              value={token}
              onChangeText={setToken}
              autoCapitalize="none"
              autoCorrect={false}
              placeholder="Incolla il token"
              placeholderTextColor={styles.muted.color}
              style={styles.input}
              accessibilityLabel="Token reset"
              testID="auth-reset-token"
            />
            <Text style={styles.label}>Nuova password</Text>
            <TextInput
              value={password}
              onChangeText={setPassword}
              secureTextEntry
              placeholder="Nuova password"
              placeholderTextColor={styles.muted.color}
              style={styles.input}
              accessibilityLabel="Nuova password"
              testID="auth-reset-password"
            />
            <Text style={styles.label}>Conferma password</Text>
            <TextInput
              value={confirmPassword}
              onChangeText={setConfirmPassword}
              secureTextEntry
              placeholder="Ripeti password"
              placeholderTextColor={styles.muted.color}
              style={styles.input}
              accessibilityLabel="Conferma password"
              testID="auth-reset-confirm-password"
            />
            <Pressable
              accessibilityRole="button"
              disabled={submitting}
              onPress={() => void onSubmit()}
              style={[styles.primaryButton, submitting && styles.disabled]}
              testID="auth-reset-submit"
            >
              <Text style={styles.primaryLabel}>
                {submitting ? "Salvataggio…" : "Salva password"}
              </Text>
            </Pressable>
            <Pressable
              accessibilityRole="button"
              onPress={() => navigation.navigate("Auth")}
              style={styles.linkRow}
              testID="auth-reset-login-link"
            >
              <Text style={styles.link}>Torna al login</Text>
            </Pressable>
          </>
        )}
      </PageContainer>
    </View>
  );
}
