import { lazyStyles } from "../theme/lazyStyles";
import { theme } from "@fantappero/ui/theme";
import { useNavigation } from "@react-navigation/core";
import type { NativeStackNavigationProp } from "@react-navigation/native-stack";
import { useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { register as registerApi } from "../api/auth";
import { AppTextInput as TextInput } from "../components/AppTextInput";
import { UiStatePanel } from "../components/UiStatePanel";
import { loadMobileEnv } from "../config/env";
import type { RootStackParamList } from "../navigation/types";
import { getApiErrorMessage, useAuthSession } from "../session/DemoSessionContext";
import { writeLastUser, type LastUser } from "../session/lastUser";
import { getMemorySession } from "../session/sessionStorage";
import { authFormStyles as styles } from "./authFormStyles";
import { AUTH_TABS, INITIAL_AUTH_TAB, type AuthTab } from "./authScreenState";
import {
  passwordAutofill,
  registrationLoginFailure,
  registrationRequestBody,
  validateEmailRegistration,
} from "./emailRegistration";
import { testerGateFromError, type TesterGateInfo } from "./testerGate";

const { colors, spacing, typography, radius } = theme;

function devApiHost(): string {
  try {
    return loadMobileEnv().expoPublicApiBaseUrl;
  } catch {
    return "EXPO_PUBLIC_API_BASE_URL mancante";
  }
}

function sameEmail(a: string, b: string): boolean {
  return a.trim().toLowerCase() === b.trim().toLowerCase();
}

/**
 * Scheda «Accedi / Registrati» con email, sotto Google nella schermata di accesso.
 * Tiene i propri campi; l'account ricordato e la richiesta tester restano ad `AuthScreen`.
 */
export function EmailAccessCard({
  remembered,
  firstName,
  onSwitchAccount,
  onClose,
  onTesterGate,
}: {
  /** Ultimo account entrato con email su questo telefono: al posto del campo email. */
  remembered: LastUser | null;
  firstName: string;
  onSwitchAccount: () => void;
  onClose: () => void;
  /** Pilota in modalità test e l'account non è tra i tester: si apre la richiesta di accesso. */
  onTesterGate: (gate: TesterGateInfo) => void;
}) {
  const navigation = useNavigation<NativeStackNavigationProp<RootStackParamList>>();
  const { login } = useAuthSession();
  const [tab, setTab] = useState<AuthTab>(INITIAL_AUTH_TAB);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loginError, setLoginError] = useState<string | null>(null);
  const [displayName, setDisplayName] = useState("");
  const [registerEmail, setRegisterEmail] = useState("");
  const [registerPassword, setRegisterPassword] = useState("");
  const [registerError, setRegisterError] = useState<string | null>(null);
  /** Conferma email accesa (es. in locale): messaggio del server dopo la registrazione. */
  const [verifyNotice, setVerifyNotice] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState<"login" | "register" | null>(null);

  function selectTab(next: AuthTab) {
    setTab(next);
    setLoginError(null);
    setRegisterError(null);
    setVerifyNotice(null);
  }

  function switchAccount() {
    setEmail("");
    setPassword("");
    setLoginError(null);
    onSwitchAccount();
  }

  /** Torna ad Accedi con l'email appena registrata già scritta. */
  function showLoginWith(prefillEmail: string, message: string | null) {
    if (remembered && !sameEmail(remembered.email, prefillEmail)) {
      onSwitchAccount();
    }
    setEmail(prefillEmail);
    setPassword("");
    setVerifyNotice(null);
    setRegisterError(null);
    setLoginError(message);
    setTab("accedi");
  }

  /** Accesso con email e password; ricorda l'account per la prossima volta. */
  async function signIn(loginEmail: string, loginPassword: string) {
    await login(loginEmail, loginPassword);
    const user = getMemorySession()?.user;
    if (user?.displayName) {
      void writeLastUser({ displayName: user.displayName, email: loginEmail });
    }
  }

  async function onLogin() {
    setLoginError(null);
    const loginEmail = (remembered?.email ?? email).trim();
    if (!loginEmail || !password) {
      setLoginError("Inserisci email e password.");
      return;
    }
    setSubmitting("login");
    try {
      await signIn(loginEmail, password);
    } catch (error) {
      // Pilota in modalità test: stessa richiesta di accesso dell'accesso con Google.
      const gate = testerGateFromError(error);
      if (gate) {
        onTesterGate(gate);
        return;
      }
      const message = getApiErrorMessage(error, "Accesso non riuscito.");
      // Solo in sviluppo: dice a quale server sta parlando l'app, per capire un «Connessione non disponibile».
      setLoginError(__DEV__ ? `${message} [API: ${devApiHost()}]` : message);
    } finally {
      setSubmitting(null);
    }
  }

  async function onRegister() {
    setRegisterError(null);
    const fields = { displayName, email: registerEmail, password: registerPassword };
    const invalid = validateEmailRegistration(fields);
    if (invalid) {
      setRegisterError(invalid);
      return;
    }
    const body = registrationRequestBody(fields);
    setSubmitting("register");
    try {
      let serverMessage: string;
      try {
        serverMessage = (await registerApi(body)).message;
      } catch (error) {
        setRegisterError(getApiErrorMessage(error, "Registrazione non riuscita."));
        return;
      }
      // Su dev e pilota la conferma email è spenta: l'account è già verificato e si entra subito.
      try {
        await signIn(body.email, body.password);
      } catch (error) {
        const outcome = registrationLoginFailure(error, getApiErrorMessage(error, "Accesso non riuscito."));
        const gate = outcome.kind === "tester_gate" ? testerGateFromError(error) : null;
        if (gate) {
          onTesterGate(gate);
        } else if (outcome.kind === "verify_email") {
          setVerifyNotice(serverMessage);
          setTab(outcome.tab);
        } else {
          showLoginWith(body.email, outcome.kind === "login_now" ? outcome.message : null);
        }
      }
    } finally {
      setSubmitting(null);
    }
  }

  return (
    <View style={cardStyles.card} testID="auth-email-card">
      <View style={cardStyles.tabs} accessibilityRole="tablist">
        {AUTH_TABS.map((item) => {
          const selected = item.key === tab;
          return (
            <Pressable
              key={item.key}
              accessibilityRole="tab"
              accessibilityLabel={item.label}
              accessibilityState={{ selected }}
              onPress={() => selectTab(item.key)}
              style={[cardStyles.tab, selected && cardStyles.tabSelected]}
              testID={item.testID}
            >
              <Text style={[cardStyles.tabLabel, selected && cardStyles.tabLabelSelected]}>{item.label}</Text>
            </Pressable>
          );
        })}
      </View>

      {tab === "accedi" ? (
        <View style={cardStyles.form} testID="auth-email-login">
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
            <View>
              <Text style={styles.label}>Email</Text>
              <TextInput
                value={email}
                onChangeText={setEmail}
                autoCapitalize="none"
                autoCorrect={false}
                autoComplete="email"
                keyboardType="email-address"
                placeholder="nome@esempio.it"
                style={styles.input}
                accessibilityLabel="Email"
                testID="auth-email"
              />
            </View>
          )}
          <View>
            <Text style={styles.label}>Password</Text>
            <TextInput
              value={password}
              onChangeText={setPassword}
              secureTextEntry
              {...passwordAutofill("login")}
              placeholder="La tua password"
              returnKeyType="go"
              onSubmitEditing={() => void onLogin()}
              style={styles.input}
              accessibilityLabel="Password"
              testID="auth-password"
            />
          </View>
          {loginError ? (
            <UiStatePanel state="error" title="Accesso non riuscito" message={loginError} testID="auth-error" />
          ) : null}
          <Pressable
            accessibilityRole="button"
            accessibilityLabel="Accedi"
            disabled={submitting !== null}
            onPress={() => void onLogin()}
            style={[styles.emailButton, cardStyles.submit, submitting !== null && styles.disabled]}
            testID="auth-login-submit"
          >
            <Text style={styles.emailButtonLabel}>
              {submitting === "login" ? "Accesso…" : remembered ? `Accedi come ${firstName}` : "Accedi"}
            </Text>
          </Pressable>
          <Pressable
            accessibilityRole="button"
            accessibilityLabel="Password dimenticata"
            onPress={() => navigation.navigate("AuthForgotPassword")}
            style={styles.centerLink}
            testID="auth-forgot-link"
          >
            <Text style={styles.linkUnderline}>Password dimenticata?</Text>
          </Pressable>
          {remembered ? (
            <Pressable accessibilityRole="button" accessibilityLabel={`Non sei ${firstName}? Cambia account`} onPress={switchAccount} style={styles.centerLink} testID="auth-not-you">
              <Text style={styles.linkUnderline}>Non sei {firstName}? Cambia account</Text>
            </Pressable>
          ) : null}
        </View>
      ) : verifyNotice ? (
        <View style={cardStyles.form}>
          <UiStatePanel state="success" title="Controlla la tua email" message={verifyNotice} testID="auth-register-success" />
          <Pressable
            accessibilityRole="button"
            onPress={() => {
              showLoginWith(registerEmail.trim(), null);
              navigation.navigate("AuthVerifyEmail");
            }}
            style={styles.centerLink}
            testID="auth-register-verify-link"
          >
            <Text style={styles.linkUnderline}>Ho un codice di verifica</Text>
          </Pressable>
          <Pressable
            accessibilityRole="button"
            onPress={() => showLoginWith(registerEmail.trim(), null)}
            style={styles.centerLink}
            testID="auth-register-back-login"
          >
            <Text style={styles.linkUnderline}>Vai ad Accedi</Text>
          </Pressable>
        </View>
      ) : (
        <View style={cardStyles.form} testID="auth-email-register">
          <View>
            <Text style={styles.label}>Nome</Text>
            <TextInput
              value={displayName}
              onChangeText={setDisplayName}
              autoComplete="name"
              placeholder="Es. Marco Rossi"
              style={styles.input}
              accessibilityLabel="Nome"
              testID="auth-register-display-name"
            />
          </View>
          <View>
            <Text style={styles.label}>Email</Text>
            <TextInput
              value={registerEmail}
              onChangeText={setRegisterEmail}
              autoCapitalize="none"
              autoCorrect={false}
              autoComplete="email"
              keyboardType="email-address"
              placeholder="nome@esempio.it"
              style={styles.input}
              accessibilityLabel="Email"
              testID="auth-register-email"
            />
          </View>
          <View>
            <Text style={styles.label}>Password</Text>
            <TextInput
              value={registerPassword}
              onChangeText={setRegisterPassword}
              secureTextEntry
              {...passwordAutofill("register")}
              placeholder="Almeno 8 caratteri"
              style={styles.input}
              accessibilityLabel="Password"
              testID="auth-register-password"
            />
          </View>
          {registerError ? (
            <UiStatePanel state="error" title="Registrazione non riuscita" message={registerError} testID="auth-register-error" />
          ) : null}
          <Pressable
            accessibilityRole="button"
            accessibilityLabel="Crea account"
            disabled={submitting !== null}
            onPress={() => void onRegister()}
            style={[styles.emailButton, cardStyles.submit, submitting !== null && styles.disabled]}
            testID="auth-register-submit"
          >
            <Text style={styles.emailButtonLabel}>{submitting === "register" ? "Registrazione…" : "Crea account"}</Text>
          </Pressable>
          <Pressable
            accessibilityRole="link"
            accessibilityLabel="Leggi l'informativa privacy"
            onPress={() => navigation.navigate("Privacy")}
            style={styles.centerLink}
            testID="auth-register-privacy-link"
          >
            <Text style={[styles.muted, cardStyles.centerText]}>
              Registrandoti accetti l&apos;<Text style={styles.linkStrong}>informativa privacy</Text>
            </Text>
          </Pressable>
        </View>
      )}

      <Pressable
        accessibilityRole="button"
        accessibilityLabel="Chiudi l'accesso con email"
        onPress={onClose}
        style={[styles.centerLink, cardStyles.close]}
        testID="auth-email-close"
      >
        <Text style={styles.muted}>Chiudi l&apos;accesso con email</Text>
      </Pressable>
    </View>
  );
}

const cardStyles = lazyStyles(() => StyleSheet.create({
  card: {
    gap: spacing.sm,
    padding: spacing.md,
    borderRadius: radius.xl,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.backgroundElevated,
  },
  tabs: {
    flexDirection: "row",
    gap: spacing.xs,
    padding: spacing.xs,
    borderRadius: radius.pill,
    backgroundColor: colors.backgroundSubtle,
  },
  tab: { flex: 1, minHeight: 40, borderRadius: radius.pill, alignItems: "center", justifyContent: "center" },
  tabSelected: { backgroundColor: colors.brand },
  tabLabel: { color: colors.foregroundMuted, fontWeight: "700", fontSize: typography.fontSize.sm },
  tabLabelSelected: { color: colors.onBrand },
  form: { gap: spacing.xs },
  submit: { marginTop: spacing.sm },
  centerText: { textAlign: "center" },
  close: { borderTopWidth: 1, borderTopColor: colors.border, marginTop: spacing.xs },
}));
