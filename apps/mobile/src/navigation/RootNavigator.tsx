import { lazyStyles } from "../theme/lazyStyles";
import { createNativeStackNavigator } from "@react-navigation/native-stack";
import { ActivityIndicator, StyleSheet, Text, View } from "react-native";
import { theme } from "@fantappero/ui/theme";
import { AuthScreen } from "../screens/AuthScreen";
import { AuthForgotPasswordScreen } from "../screens/AuthForgotPasswordScreen";
import { AuthRegisterScreen } from "../screens/AuthRegisterScreen";
import { AuthResetPasswordScreen } from "../screens/AuthResetPasswordScreen";
import { AuthVerifyEmailScreen } from "../screens/AuthVerifyEmailScreen";
import { CreateLeagueScreen } from "../screens/CreateLeagueScreen";
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
import { buildSceneBackgroundStyle } from "../theme/navigationTheme";
import { AdminNavigator } from "./AdminNavigator";
import { AppTabNavigator } from "./AppTabNavigator";
import type { RootStackParamList } from "./types";

const Stack = createNativeStackNavigator<RootStackParamList>();
const { colors, spacing, typography } = theme;

const CreateLeagueWithCountdown = withLockCountdown(CreateLeagueScreen);
const LeagueHomeWithCountdown = withLockCountdown(LeagueHomeScreen);
const LeagueAdminWithCountdown = withLockCountdown(LeagueAdminScreen);
const JoinLeagueWithCountdown = withLockCountdown(JoinLeagueScreen);
const ReceivedInvitesWithCountdown = withLockCountdown(ReceivedInvitesScreen);
const NotificationsWithCountdown = withLockCountdown(NotificationsScreen);
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

/** Gate auth come web RequireAuth: senza sessione → Accedi; dopo login → app. */
export function RootNavigator() {
  const { isAuthenticated, loading } = useAuthSession();

  if (loading) {
    return <SessionLoadingScreen />;
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
}));
