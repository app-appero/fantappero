import { useNavigation } from "@react-navigation/core";
import type { NativeStackNavigationProp } from "@react-navigation/native-stack";
import { theme } from "@fantappero/ui/theme";
import { useEffect, useState } from "react";
import Ionicons from "@expo/vector-icons/Ionicons";
import { Pressable, Text, View } from "react-native";
import { useAuthOptions } from "../auth/useAuthOptions";
import { useGoogleAuth } from "../auth/useGoogleAuth";
import { AuthShell } from "../auth/AuthShell";
import { authFormStyles } from "../auth/authFormStyles";
import { resolveAuthScreenView } from "../auth/authScreenState";
import { EmailAccessCard } from "../auth/EmailAccessCard";
import { LoginCards } from "../auth/LoginCards";
import { TesterRequestPanel } from "../auth/TesterRequestPanel";
import type { TesterGateInfo } from "../auth/testerGate";
import { UiStatePanel } from "../components/UiStatePanel";
import type { RootStackParamList } from "../navigation/types";
import { getApiErrorMessage, useAuthSession } from "../session/DemoSessionContext";
import { clearLastUser, readLastUser, type LastUser } from "../session/lastUser";

/**
 * Accesso con Apple: per ora nascosto (arriverà con la versione iPhone, Fase 2).
 * Per rimetterlo come tasto disabilitato basta impostare `true`.
 */
const SHOW_APPLE_SIGN_IN = false;

const { colors } = theme;

/**
 * Login — allineato a web /accedi. Google è l'accesso principale; se il server ha la
 * registrazione con email attiva, sotto c'è «Continua con email» che apre la scheda
 * Accedi / Registrati (decisioni in `auth/authScreenState.ts`).
 */
export function AuthScreen() {
  const navigation = useNavigation<NativeStackNavigationProp<RootStackParamList>>();
  const { claimGoogleHandoff } = useAuthSession();
  const [error, setError] = useState<string | null>(null);
  const [googleSubmitting, setGoogleSubmitting] = useState(false);
  const [remembered, setRemembered] = useState<LastUser | null>(null);
  /** Scelta dell'utente sulla scheda con email: `null` finché non la apre o chiude. */
  const [expandedChoice, setExpandedChoice] = useState<boolean | null>(null);
  /** Rifiuto `tester_only` dell'accesso con email: al posto della schermata, la richiesta. */
  const [testerGate, setTesterGate] = useState<TesterGateInfo | null>(null);
  useEffect(() => {
    void readLastUser().then((last) => {
      if (last) {
        setRemembered(last);
      }
    });
  }, []);
  const firstName = remembered?.displayName.trim().split(/\s+/)[0] ?? "";

  function switchAccount() {
    setRemembered(null);
    setError(null);
    void clearLastUser();
  }
  const googleAuth = useGoogleAuth((code) => {
    setError(null);
    setGoogleSubmitting(true);
    return claimGoogleHandoff(code)
      .catch((googleError: unknown) => {
        setError(getApiErrorMessage(googleError, "Accesso con Google non riuscito."));
      })
      .finally(() => {
        setGoogleSubmitting(false);
      });
  });

  // Pilota: con la registrazione con email spenta anche l'accesso è solo con Google.
  // Finché il server non risponde non si mostra l'email; se la richiesta fallisce nemmeno.
  const authOptions = useAuthOptions();
  const view = resolveAuthScreenView({
    optionsLoaded: authOptions.loaded,
    emailRegistrationEnabled: authOptions.emailRegistrationEnabled,
    googleAvailable: googleAuth.available,
    expandedChoice,
  });
  const googleLabel = remembered ? `Continua come ${firstName} con Google` : "Continua con Google";

  if (testerGate) {
    return (
      <AuthShell testID="screen-auth" onBack={() => setTesterGate(null)}>
        <TesterRequestPanel info={testerGate} onBack={() => setTesterGate(null)} />
      </AuthShell>
    );
  }

  return (
    <AuthShell
      testID="screen-auth"
      footer={
        <>
          {googleAuth.available ? (
            <Pressable
              accessibilityRole="button"
              accessibilityLabel={googleLabel}
              disabled={googleSubmitting}
              onPress={() => {
                void googleAuth.promptAsync().catch((googleError: unknown) => {
                  setError(getApiErrorMessage(googleError, "Accesso con Google non riuscito."));
                });
              }}
              style={[styles.googleMain, googleSubmitting && styles.disabled]}
              testID="auth-google-submit"
            >
              <View style={styles.googleMarkMain}>
                <Text style={styles.googleMarkLabel}>G</Text>
              </View>
              <Text style={styles.googleMainLabel}>{googleSubmitting ? "Accesso…" : googleLabel}</Text>
            </Pressable>
          ) : null}
          {view.showGoogleNote ? (
            <Text style={[styles.muted, styles.googleNote]}>Entri in un tocco: niente password da ricordare</Text>
          ) : null}
          {__DEV__ && !googleAuth.available ? (
            <Text style={styles.muted} testID="auth-dev-google-hint">
              Solo sviluppo: «Continua con Google» è nascosto perché manca EXPO_PUBLIC_GOOGLE_CLIENT_ID_WEB o
              EXPO_PUBLIC_WEB_BASE_URL. Avvia Expo con «pnpm start:pilota».
            </Text>
          ) : null}
          {SHOW_APPLE_SIGN_IN ? (
            <View style={styles.appleDisabled} accessibilityRole="button" accessibilityState={{ disabled: true }} accessibilityLabel="Continua con Apple, disponibile presto" testID="auth-apple-disabled">
              <Ionicons name="logo-apple" size={22} color={colors.foreground} />
              <Text style={styles.appleLabel}>Continua con Apple</Text>
            </View>
          ) : null}
          {view.dividerLabel ? (
            <View style={styles.orRow} testID="auth-email-divider">
              <View style={styles.orLine} />
              <Text style={styles.muted}>{view.dividerLabel}</Text>
              <View style={styles.orLine} />
            </View>
          ) : null}
          {view.showEmailToggle ? (
            <Pressable
              accessibilityRole="button"
              accessibilityLabel="Continua con email"
              accessibilityState={{ expanded: false }}
              onPress={() => {
                setError(null);
                setExpandedChoice(true);
              }}
              style={styles.emailToggle}
              testID="auth-email-toggle"
            >
              <Ionicons name="mail-outline" size={22} color={colors.foreground} />
              <Text style={styles.emailToggleLabel}>Continua con email</Text>
            </Pressable>
          ) : null}
          {view.showEmailCard ? (
            <EmailAccessCard
              remembered={remembered}
              firstName={firstName}
              onSwitchAccount={switchAccount}
              onClose={() => setExpandedChoice(false)}
              onTesterGate={setTesterGate}
            />
          ) : null}
          <Pressable
            accessibilityRole="link"
            accessibilityLabel="Leggi l'informativa privacy"
            onPress={() => navigation.navigate("Privacy")}
            style={styles.centerLink}
            testID="auth-privacy-link"
          >
            <Text style={styles.muted}>
              Accedendo accetti l'<Text style={styles.linkStrong}>informativa privacy</Text>
            </Text>
          </Pressable>
        </>
      }
    >
      <View testID="screen-auth-form">
        <LoginCards firstName={remembered ? firstName : undefined} compact={!view.showCardsStage} />
        {error ? (
          <UiStatePanel state="error" title="Accesso non riuscito" message={error} testID="auth-error" />
        ) : null}
      </View>
    </AuthShell>
  );
}

/** Stili condivisi: ora in `auth/authFormStyles.ts`, riesportati per le altre schermate di accesso. */
export { authFormStyles, authPageStyles } from "../auth/authFormStyles";

const styles = authFormStyles;
