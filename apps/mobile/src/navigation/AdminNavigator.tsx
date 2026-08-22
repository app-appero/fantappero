import { createNativeStackNavigator } from "@react-navigation/native-stack";
import { StyleSheet, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { theme } from "@fantappero/ui/theme";
import { AppHeader } from "../layout/AppHeader";
import { AdminDashboardScreen } from "../screens/admin/AdminDashboardScreen";
import { AdminLeaguesScreen } from "../screens/admin/AdminLeaguesScreen";
import { AdminListoneScreen } from "../screens/admin/AdminListoneScreen";
import { AdminUsersScreen } from "../screens/admin/AdminUsersScreen";
import { useAuthSession } from "../session/DemoSessionContext";
import { NAV_LABELS } from "./navConfig";
import type { AdminStackParamList } from "./types";
import type { NativeStackNavigationProp } from "@react-navigation/native-stack";
import type { RootStackParamList } from "./types";
import { useNavigation } from "@react-navigation/core";
import { sceneBackgroundStyle } from "../theme/navigationTheme";

const Stack = createNativeStackNavigator<AdminStackParamList>();
const { colors } = theme;

function AdminShell({ children }: { children: React.ReactNode }) {
  const insets = useSafeAreaInsets();
  const navigation = useNavigation<NativeStackNavigationProp<RootStackParamList>>();
  const { user, logout } = useAuthSession();

  return (
    <View style={[styles.shell, { paddingTop: insets.top }]}>
      <AppHeader
        surface="admin"
        userDisplayName={user?.displayName ?? "Operatore"}
        onBrandPress={() => navigation.navigate("AdminPanel")}
        onBackToAppPress={() => navigation.navigate("MainTabs")}
        showLogout
        onLogoutPress={() => void logout()}
      />
      <View style={styles.content}>{children}</View>
    </View>
  );
}

/**
 * Global operator panel stack (EP11-04a/b/EP11-05 mobile parity).
 * The dashboard links to the other three sections (mirrors the web `AdminLayout` sidebar,
 * which has no mobile equivalent — the native stack header back button returns to it).
 */
export function AdminNavigator() {
  return (
    <AdminShell>
      <Stack.Navigator screenOptions={{ headerShown: false, contentStyle: sceneBackgroundStyle }}>
        <Stack.Screen name="AdminHome" options={{ title: NAV_LABELS["admin-home"] }}>
          {() => <AdminDashboardScreen />}
        </Stack.Screen>
        <Stack.Screen name="AdminLeagues" options={{ title: NAV_LABELS["admin-leagues"] }}>
          {() => <AdminLeaguesScreen />}
        </Stack.Screen>
        <Stack.Screen name="AdminUsers" options={{ title: NAV_LABELS["admin-users"] }}>
          {() => <AdminUsersScreen />}
        </Stack.Screen>
        <Stack.Screen name="AdminListone" options={{ title: NAV_LABELS["admin-listone"] }}>
          {() => <AdminListoneScreen />}
        </Stack.Screen>
      </Stack.Navigator>
    </AdminShell>
  );
}

const styles = StyleSheet.create({
  shell: {
    flex: 1,
    backgroundColor: colors.background,
  },
  content: {
    flex: 1,
  },
});
