import { useNavigation } from "@react-navigation/core";
import type { NativeStackNavigationProp } from "@react-navigation/native-stack";
import { useState } from "react";
import { Pressable, Text, TextInput, View } from "react-native";
import { register as registerApi } from "../api/auth";
import { BrandLogo } from "../components/BrandLogo";
import { UiStatePanel } from "../components/UiStatePanel";
import { PageContainer } from "../layout/PageContainer";
import type { RootStackParamList } from "../navigation/types";
import { getApiErrorMessage } from "../session/DemoSessionContext";
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
    <View style={styles.root} testID="screen-auth-register">
      <PageContainer title="Registrati" testID="screen-auth-register-form">
        <View style={styles.brand}>
          <BrandLogo variant="full" size="lg" />
        </View>
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
              onPress={() => navigation.navigate("Auth")}
              style={styles.linkRow}
              testID="auth-register-back-login"
            >
              <Text style={styles.link}>Torna al login</Text>
            </Pressable>
          </>
        ) : (
          <>
            <Text style={styles.lead}>Crea il tuo account FantApperò.</Text>
            {error ? (
              <UiStatePanel
                state="error"
                title="Registrazione non riuscita"
                message={error}
                testID="auth-register-error"
              />
            ) : null}
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
              placeholder="tu@email.it"
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
              placeholder="Password"
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
              placeholder="Ripeti password"
              placeholderTextColor={styles.muted.color}
              style={styles.input}
              accessibilityLabel="Conferma password"
              testID="auth-register-confirm-password"
            />
            <Pressable
              accessibilityRole="button"
              disabled={submitting}
              onPress={() => void onSubmit()}
              style={[styles.primaryButton, submitting && styles.disabled]}
              testID="auth-register-submit"
            >
              <Text style={styles.primaryLabel}>
                {submitting ? "Registrazione…" : "Registrati"}
              </Text>
            </Pressable>
            <Pressable
              accessibilityRole="button"
              onPress={() => navigation.navigate("Auth")}
              style={styles.linkRow}
              testID="auth-register-login-link"
            >
              <Text style={styles.muted}>
                Hai già un account? <Text style={styles.link}>Accedi</Text>
              </Text>
            </Pressable>
          </>
        )}
      </PageContainer>
    </View>
  );
}
