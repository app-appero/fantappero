import { useFocusEffect, useNavigation, useNavigationState } from "@react-navigation/core";
import { createNativeStackNavigator } from "@react-navigation/native-stack";
import type { NativeStackNavigationProp } from "@react-navigation/native-stack";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { StyleSheet, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { theme } from "@fantappero/ui/theme";
import { AppDrawer } from "../components/AppDrawer";
import { ImpersonationBanner } from "../components/ImpersonationBanner";
import { AppHeader } from "../layout/AppHeader";
import { AdminDashboardScreen } from "../screens/admin/AdminDashboardScreen";
import { AdminLeaguesScreen } from "../screens/admin/AdminLeaguesScreen";
import { AdminListoneScreen } from "../screens/admin/AdminListoneScreen";
import { AdminTurniScreen } from "../screens/admin/AdminTurniScreen";
import { AdminUsersScreen } from "../screens/admin/AdminUsersScreen";
import { useAuthSession } from "../session/DemoSessionContext";
import { consumePendingAdminScreen, openAdminScreen, registerLeaveAdmin } from "./adminEntry";
import { filterMobileNavItems, MOBILE_ADMIN_NAV_ITEMS } from "./navConfig";
import type { AdminStackParamList, RootStackParamList } from "./types";
import { sceneBackgroundStyle } from "../theme/navigationTheme";

const Stack = createNativeStackNavigator<AdminStackParamList>();
const { colors } = theme;

const ADMIN_SCREEN_BY_ID: Record<string, keyof AdminStackParamList> = {
  "admin-home": "AdminHome",
  "admin-leagues": "AdminLeagues",
  "admin-users": "AdminUsers",
  "admin-listone": "AdminListone",
  "admin-turni": "AdminTurni",
};

const ADMIN_NAV_ID_BY_ROUTE: Record<string, string> = {
  AdminHome: "admin-home",
  AdminLeagues: "admin-leagues",
  AdminUsers: "admin-users",
  AdminListone: "admin-listone",
  AdminTurni: "admin-turni",
};

/**
 * Pannello operatore: le sezioni si aprono dal menu in alto a sinistra,
 * come il drawer del sito su mobile.
 */
export function AdminNavigator() {
  const insets = useSafeAreaInsets();
  const rootNavigation = useNavigation<NativeStackNavigationProp<RootStackParamList>>();
  const { user, logout, can, isImpersonating, stopImpersonation } = useAuthSession();
  const [drawerOpen, setDrawerOpen] = useState(false);
  const stackNavigation = useRef<NativeStackNavigationProp<AdminStackParamList> | null>(null);
  const drawerItems = useMemo(() => filterMobileNavItems(MOBILE_ADMIN_NAV_ITEMS, can), [can]);

  const activeRouteName = useNavigationState((state) => {
    const route = state.routes[state.index];
    if (!route || route.name !== "AdminPanel") {
      return "AdminHome";
    }
    const nested = route.state;
    if (nested && typeof nested.index === "number") {
      return String(nested.routes[nested.index]?.name ?? "AdminHome");
    }
    return "AdminHome";
  });

  const openPendingScreen = useCallback(() => {
    const pending = consumePendingAdminScreen();
    if (pending) {
      stackNavigation.current?.navigate(pending);
    }
  }, []);

  useFocusEffect(
    useCallback(() => {
      openPendingScreen();
    }, [openPendingScreen]),
  );

  useEffect(() => {
    return registerLeaveAdmin(() => {
      openAdminScreen("AdminUsers");
      rootNavigation.navigate("MainTabs");
    });
  }, [rootNavigation]);

  function rememberStack(navigation: NativeStackNavigationProp<AdminStackParamList>) {
    stackNavigation.current = navigation;
  }

  function closeDrawer() {
    setDrawerOpen(false);
  }

  return (
    <View style={[styles.shell, { paddingTop: insets.top }]}>
      {isImpersonating ? (
        <ImpersonationBanner
          displayName={user?.displayName ?? "un utente"}
          onExit={async () => {
            await stopImpersonation();
            rootNavigation.navigate("MainTabs");
          }}
        />
      ) : null}
      <AppHeader
        surface="admin"
        userDisplayName={user?.displayName ?? "Operatore"}
        showMenuButton
        onMenuPress={() => setDrawerOpen(true)}
        onBrandPress={() => stackNavigation.current?.navigate("AdminHome")}
        showLogout
        onLogoutPress={() => void logout()}
      />
      <View style={styles.content}>
        <Stack.Navigator screenOptions={{ headerShown: false, contentStyle: sceneBackgroundStyle }}>
          <Stack.Screen name="AdminHome">
            {({ navigation }) => {
              rememberStack(navigation);
              return <AdminDashboardScreen />;
            }}
          </Stack.Screen>
          <Stack.Screen name="AdminLeagues">
            {({ navigation }) => {
              rememberStack(navigation);
              return <AdminLeaguesScreen />;
            }}
          </Stack.Screen>
          <Stack.Screen name="AdminUsers">
            {({ navigation }) => {
              rememberStack(navigation);
              return <AdminUsersScreen />;
            }}
          </Stack.Screen>
          <Stack.Screen name="AdminListone">
            {({ navigation }) => {
              rememberStack(navigation);
              return <AdminListoneScreen />;
            }}
          </Stack.Screen>
          <Stack.Screen name="AdminTurni">
            {({ navigation }) => {
              rememberStack(navigation);
              return <AdminTurniScreen />;
            }}
          </Stack.Screen>
        </Stack.Navigator>
      </View>
      <AppDrawer
        visible={drawerOpen}
        items={drawerItems}
        userDisplayName={user?.displayName ?? "Operatore"}
        activeItemId={ADMIN_NAV_ID_BY_ROUTE[activeRouteName] ?? null}
        onClose={closeDrawer}
        onNavigate={(item) => {
          closeDrawer();
          const screen = ADMIN_SCREEN_BY_ID[item.id];
          if (screen) {
            stackNavigation.current?.navigate(screen);
          }
        }}
        onBackToAppPress={() => {
          closeDrawer();
          rootNavigation.navigate("MainTabs");
        }}
        onLogout={() => {
          closeDrawer();
          void logout();
        }}
      />
    </View>
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
