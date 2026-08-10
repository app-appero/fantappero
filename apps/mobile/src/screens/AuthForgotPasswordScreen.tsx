import { useNavigation } from "@react-navigation/core";
import type { NativeStackNavigationProp } from "@react-navigation/native-stack";
import { useState } from "react";
import { Pressable, Text, TextInput, View } from "react-native";
import { forgotPassword } from "../api/auth";
import { BrandLogo } from "../components/BrandLogo";
import { UiStatePanel } from "../components/UiStatePanel";
import { PageContainer } from "../layout/PageContainer";
import type { RootStackParamList } from "../navigation/types";
import { getApiErrorMessage } from "../session/DemoSessionContext";
import { authFormStyles as styles } from "./AuthScreen";

/** Recupero password — allineato a web /accedi/recupera. */
export function AuthForgotPasswordScreen() {
  const navigation = useNavigation<NativeStackNavigationProp<RootStackParamList>>();
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
    <View style={styles.root} testID="screen-auth-forgot">
      <PageContainer title="Recupera accesso" testID="screen-auth-forgot-form">
        <View style={styles.brand}>
          <BrandLogo variant="full" size="lg" />
        </View>
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
      </PageContainer>
    </View>
  );
}
