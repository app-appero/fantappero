import { lazyStyles } from "../theme/lazyStyles";
import { createNativeStackNavigator } from "@react-navigation/native-stack";
import { ActivityIndicator, Pressable, StyleSheet, Text, View } from "react-native";
import { theme } from "@fantappero/ui/theme";
import { AuthScreen } from "../screens/AuthScreen";
import { AuthForgotPasswordScreen } from "../screens/AuthForgotPasswordScreen";
import { AuthRegisterScreen } from "../screens/AuthRegisterScreen";
import { AuthResetPasswordScreen } from "../screens/AuthResetPasswordScreen";
import { AuthVerifyEmailScreen } from "../screens/AuthVerifyEmailScreen";
import { CreateLeagueScreen } from "../screens/CreateLeagueScreen";
import { FaqScreen } from "../screens/FaqScreen";
import { FeedbackScreen } from "../screens/FeedbackScreen";
import { PrivacyScreen } from "../screens/PrivacyScreen";
import { JoinLeagueScreen } from "../screens/JoinLeagueScreen";
import { LeagueAdminScreen } from "../screens/LeagueAdminScreen";
import { LeagueHomeScreen } from "../screens/LeagueHomeScreen";
import { CoachProfileScreen } from "../screens/CoachProfileScreen";
import { ManagerDirectoryScreen } from "../screens/ManagerDirectoryScreen";
import { FixtureDetailScreen } from "../screens/FixtureDetailScreen";
import { MatchupDetailScreen } from "../screens/MatchupDetailScreen";
import { NotificationsScreen } from "../screens/NotificationsScreen";
import { ReceivedInvitesScreen } from "../screens/ReceivedInvitesScreen";
import { withLockCountdown } from "../layout/LockCountdownBar";
import { useAuthSession } from "../session/DemoSessionContext";
import { startupGate } from "../session/startupRestore";
import { buildSceneBackgroundStyle } from "../theme/navigationTheme";
import { AdminNavigator } from "./AdminNavigator";
import { AppTabNavigator } from "./AppTabNavigator";
import type { RootStackParamList } from "./types";

const Stack = createNativeStackNavigator<RootStackParamList>();
const { colors, spacing, typography, radius } = theme;

const CreateLeagueWithCountdown = withLockCountdown(CreateLeagueScreen);
const LeagueHomeWithCountdown = withLockCountdown(LeagueHomeScreen);
const LeagueAdminWithCountdown = withLockCountdown(LeagueAdminScreen);
const JoinLeagueWithCountdown = withLockCountdown(JoinLeagueScreen);
const ReceivedInvitesWithCountdown = withLockCountdown(ReceivedInvitesScreen);
const NotificationsWithCountdown = withLockCountdown(NotificationsScreen);
const FeedbackWithCountdown = withLockCountdown(FeedbackScreen);
const FaqWithCountdown = withLockCountdown(FaqScreen);
const ManagerDirectoryWithCountdown = withLockCountdown(ManagerDirectoryScreen);
const CoachProfileWithCountdown = withLockCountdown(CoachProfileScreen);
const MatchupDetailWithCountdown = withLockCountdown(MatchupDetailScreen);
const FixtureDetailWithCountdown = withLockCountdown(FixtureDetailScreen);

function SessionLoadingScreen() {
  return (
    <View style={styles.loadingRoot} testID="auth-loading">
      <ActivityIndicator color={colors.accent} size="large" />
      <Text style={styles.loadingTitle}>Caricamento sessione</Text>
      <Text style={styles.loadingMessage}>Stiamo verificando le tue credenziali…</Text>
    </View>
  );
}

/**
 * Avvio senza rete con una sessione salvata (corsa M5, 22/11): al posto di «Bentornato» un
 * messaggio di rete con «Riprova». L'app riprova anche da sola (vedi `DemoSessionContext`) e
 * appena il server risponde entra con la stessa sessione, senza chiedere la password.
 */
function SessionOfflineScreen() {
  const { restoringSession, retrySessionRestore } = useAuthSession();
  return (
    <View style={styles.loadingRoot} testID="auth-offline">
      <Text style={styles.loadingTitle} accessibilityRole="header">
        Connessione non disponibile
      </Text>
      <Text style={styles.loadingMessage}>
        Non riusciamo a raggiungere FantApperò. Controlla la rete: appena torna l&apos;app riparte da
        sola, senza rifare l&apos;accesso.
      </Text>
      <Pressable
        accessibilityRole="button"
        accessibilityState={{ busy: restoringSession, disabled: restoringSession }}
        disabled={restoringSession}
        onPress={() => void retrySessionRestore()}
        style={[styles.retryButton, restoringSession && styles.retryButtonBusy]}
        testID="auth-offline-retry"
      >
        {restoringSession ? <ActivityIndicator color={colors.onBrand} /> : null}
        <Text style={styles.retryLabel}>{restoringSession ? "Riprovo…" : "Riprova"}</Text>
      </Pressable>
    </View>
  );
}

/** Gate auth come web RequireAuth: senza sessione → Accedi; dopo login → app. */
export function RootNavigator() {
  const { isAuthenticated, loading, sessionOffline } = useAuthSession();
  const gate = startupGate({ loading, isAuthenticated, sessionOffline });

  if (gate === "loading") {
    return <SessionLoadingScreen />;
  }
  if (gate === "offline") {
    return <SessionOfflineScreen />;
  }

  return (
    <Stack.Navigator
      key={isAuthenticated ? "app" : "auth"}
      screenOptions={{
        headerStyle: { backgroundColor: colors.backgroundElevated },
        headerTintColor: colors.foreground,
        headerTitleStyle: { color: colors.foreground },
        contentStyle: buildSceneBackgroundStyle(),
      }}
    >
      {!isAuthenticated ? (
        <>
          <Stack.Screen
            name="Auth"
            component={AuthScreen}
            options={{ title: "Accedi", headerShown: false }}
          />
          <Stack.Screen
            name="Privacy"
            component={PrivacyScreen}
            options={{ title: "Privacy" }}
          />
          <Stack.Screen
            name="AuthRegister"
            component={AuthRegisterScreen}
            options={{ title: "Registrati", headerShown: false }}
          />
          <Stack.Screen
            name="AuthForgotPassword"
            component={AuthForgotPasswordScreen}
            options={{ title: "Recupera accesso", headerShown: false }}
          />
          <Stack.Screen
            name="AuthResetPassword"
            component={AuthResetPasswordScreen}
            options={{ title: "Reimposta password", headerShown: false }}
          />
          <Stack.Screen
            name="AuthVerifyEmail"
            component={AuthVerifyEmailScreen}
            options={{ title: "Verifica email", headerShown: false }}
          />
        </>
      ) : (
        <>
          <Stack.Screen
            name="MainTabs"
            component={AppTabNavigator}
            options={{ headerShown: false }}
          />
          <Stack.Screen
            name="CreateLeague"
            component={CreateLeagueWithCountdown}
            options={{ title: "Crea lega" }}
          />
          <Stack.Screen
            name="LeagueHome"
            component={LeagueHomeWithCountdown}
            options={{ title: "Home lega" }}
          />
          <Stack.Screen
            name="LeagueAdmin"
            component={LeagueAdminWithCountdown}
            options={{ title: "Admin lega" }}
          />
          <Stack.Screen
            name="JoinLeague"
            component={JoinLeagueWithCountdown}
            options={{ title: "Entra in una lega" }}
          />
          <Stack.Screen
            name="ReceivedInvites"
            component={ReceivedInvitesWithCountdown}
            options={{ title: "Inviti ricevuti" }}
          />
          <Stack.Screen
            name="Notifications"
            component={NotificationsWithCountdown}
            options={{ title: "Notifiche" }}
          />
          <Stack.Screen
            name="Privacy"
            component={PrivacyScreen}
            options={{ title: "Privacy" }}
          />
          <Stack.Screen
            name="Feedback"
            component={FeedbackWithCountdown}
            options={{ title: "Segnala un problema" }}
          />
          <Stack.Screen
            name="Faq"
            component={FaqWithCountdown}
            options={{ title: "Domande frequenti" }}
          />
          <Stack.Screen
            name="ManagerDirectory"
            component={ManagerDirectoryWithCountdown}
            options={{ title: "Fantallenatori" }}
          />
          <Stack.Screen
            name="CoachProfile"
            component={CoachProfileWithCountdown}
            options={{ title: "Profilo fantallenatore" }}
          />
          <Stack.Screen
            name="MatchupDetail"
            component={MatchupDetailWithCountdown}
            options={{ title: "Scontro diretto" }}
          />
          <Stack.Screen
            name="FixtureDetail"
            component={FixtureDetailWithCountdown}
            options={{ title: "Partita" }}
          />
          <Stack.Screen
            name="AdminPanel"
            component={AdminNavigator}
            options={{ headerShown: false }}
          />
        </>
      )}
    </Stack.Navigator>
  );
}

const styles = lazyStyles(() => StyleSheet.create({
  loadingRoot: {
    flex: 1,
    backgroundColor: colors.background,
    alignItems: "center",
    justifyContent: "center",
    gap: spacing.sm,
    padding: spacing.lg,
  },
  loadingTitle: {
    color: colors.foreground,
    fontSize: typography.fontSize.lg,
    fontWeight: typography.fontWeight.semibold,
  },
  loadingMessage: {
    color: colors.foregroundMuted,
    fontSize: typography.fontSize.sm,
    textAlign: "center",
  },
  retryButton: {
    marginTop: spacing.md,
    minHeight: 48,
    minWidth: 160,
    paddingHorizontal: spacing.lg,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: spacing.sm,
    borderRadius: radius.pill,
    backgroundColor: colors.brand,
  },
  retryButtonBusy: {
    opacity: 0.7,
  },
  retryLabel: {
    color: colors.onBrand,
    fontSize: typography.fontSize.md,
    fontWeight: typography.fontWeight.semibold,
  },
}));
