import { createNativeStackNavigator } from "@react-navigation/native-stack";
import { ActivityIndicator, StyleSheet, Text, View } from "react-native";
import { theme } from "@fantappero/ui/theme";
import { AuthScreen } from "../screens/AuthScreen";
import { AuthForgotPasswordScreen } from "../screens/AuthForgotPasswordScreen";
import { AuthRegisterScreen } from "../screens/AuthRegisterScreen";
import { AuthResetPasswordScreen } from "../screens/AuthResetPasswordScreen";
import { CreateLeagueScreen } from "../screens/CreateLeagueScreen";
import { JoinLeagueScreen } from "../screens/JoinLeagueScreen";
import { LeagueAdminScreen } from "../screens/LeagueAdminScreen";
import { LeagueHomeScreen } from "../screens/LeagueHomeScreen";
import { ManagerDirectoryScreen } from "../screens/ManagerDirectoryScreen";
import { ReceivedInvitesScreen } from "../screens/ReceivedInvitesScreen";
import { useAuthSession } from "../session/DemoSessionContext";
import { sceneBackgroundStyle } from "../theme/navigationTheme";
import { AdminNavigator } from "./AdminNavigator";
import { AppTabNavigator } from "./AppTabNavigator";
import type { RootStackParamList } from "./types";

const Stack = createNativeStackNavigator<RootStackParamList>();
const { colors, spacing, typography } = theme;

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
        contentStyle: sceneBackgroundStyle,
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
            component={CreateLeagueScreen}
            options={{ title: "Crea lega" }}
          />
          <Stack.Screen
            name="LeagueHome"
            component={LeagueHomeScreen}
            options={{ title: "Home lega" }}
          />
          <Stack.Screen
            name="LeagueAdmin"
            component={LeagueAdminScreen}
            options={{ title: "Admin lega" }}
          />
          <Stack.Screen
            name="JoinLeague"
            component={JoinLeagueScreen}
            options={{ title: "Entra in una lega" }}
          />
          <Stack.Screen
            name="ReceivedInvites"
            component={ReceivedInvitesScreen}
            options={{ title: "Inviti ricevuti" }}
          />
          <Stack.Screen
            name="ManagerDirectory"
            component={ManagerDirectoryScreen}
            options={{ title: "Fantallenatori" }}
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

const styles = StyleSheet.create({
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
});
