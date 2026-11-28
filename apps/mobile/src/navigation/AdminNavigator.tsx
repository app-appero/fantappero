import { lazyStyles } from "../theme/lazyStyles";
import { useFocusEffect, useNavigation, useNavigationState } from "@react-navigation/core";
import { createNativeStackNavigator } from "@react-navigation/native-stack";
import type { NativeStackNavigationProp } from "@react-navigation/native-stack";
import { useCallback, useEffect, useMemo, useRef, useState, type ComponentType } from "react";
import { StyleSheet, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { theme } from "@fantappero/ui/theme";
import { AdminBackBar } from "../components/AdminBackBar";
import { AppDrawer } from "../components/AppDrawer";
import { ImpersonationBanner } from "../components/ImpersonationBanner";
import { AppHeader } from "../layout/AppHeader";
import { LockCountdownBar } from "../layout/LockCountdownBar";
import { AdminDashboardScreen } from "../screens/admin/AdminDashboardScreen";
import { AdminLeaguesScreen } from "../screens/admin/AdminLeaguesScreen";
import { AdminListoneScreen } from "../screens/admin/AdminListoneScreen";
import { AdminEmailScreen } from "../screens/admin/AdminEmailScreen";
import { AdminFeedbackScreen } from "../screens/admin/AdminFeedbackScreen";
import { AdminNotificationsScreen } from "../screens/admin/AdminNotificationsScreen";
import { AdminJobsScreen } from "../screens/admin/AdminJobsScreen";
import { AdminTurniScreen } from "../screens/admin/AdminTurniScreen";
import { AdminUsersScreen } from "../screens/admin/AdminUsersScreen";
import { useAuthSession } from "../session/DemoSessionContext";
import { AdminAppVersionScreen } from "../screens/admin/AdminAppVersionScreen";
import { consumePendingAdminScreen, openAdminScreen, registerLeaveAdmin } from "./adminEntry";
import { ADMIN_NAV_ID_BY_ROUTE, ADMIN_SCREEN_BY_ID, adminBackTarget } from "./adminScreens";
import { filterMobileNavItems, MOBILE_ADMIN_NAV_ITEMS } from "./navConfig";
import type { AdminStackParamList, RootStackParamList } from "./types";
import { buildSceneBackgroundStyle } from "../theme/navigationTheme";

const Stack = createNativeStackNavigator<AdminStackParamList>();
const { colors } = theme;

/** Le schermate del pannello, nell'ordine dello stack; «AdminHome» (Riepilogo) è la prima. */
const ADMIN_STACK_SCREENS: ReadonlyArray<[keyof AdminStackParamList, ComponentType]> = [
  ["AdminHome", AdminDashboardScreen],
  ["AdminLeagues", AdminLeaguesScreen],
  ["AdminUsers", AdminUsersScreen],
  ["AdminListone", AdminListoneScreen],
  ["AdminTurni", AdminTurniScreen],
  ["AdminJobs", AdminJobsScreen],
  ["AdminEmail", AdminEmailScreen],
  ["AdminFeedback", AdminFeedbackScreen],
  ["AdminNotifications", AdminNotificationsScreen],
  ["AdminAppVersion", AdminAppVersionScreen],
];

/**
 * Pannello operatore: le sezioni si aprono dal menu in alto a sinistra,
 * come il drawer del sito su mobile.
 */
export function AdminNavigator() {
  const insets = useSafeAreaInsets();
  const rootNavigation = useNavigation<NativeStackNavigationProp<RootStackParamList>>();

  /** Torna all'app azzerando lo stack: niente schermata utente (es. Segnalazioni) rimasta sotto. */
  function goToApp() {
    rootNavigation.reset({ index: 0, routes: [{ name: "MainTabs" }] });
  }
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
      goToApp();
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
            goToApp();
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
      <LockCountdownBar />
      <View style={styles.content}>
        <Stack.Navigator screenOptions={{ headerShown: false, contentStyle: buildSceneBackgroundStyle() }}>
          {ADMIN_STACK_SCREENS.map(([name, Screen]) => (
            <Stack.Screen key={name} name={name}>
              {({ navigation }) => {
                rememberStack(navigation);
                return (
                  <View style={styles.content}>
                    {/* 1.5: «Indietro» ben visibile in ogni schermata del pannello. */}
                    <AdminBackBar
                      onPress={() => {
                        const target = adminBackTarget({
                          screen: name,
                          canGoBack: navigation.canGoBack(),
                        });
                        if (target === "back") {
                          navigation.goBack();
                        } else if (target === "home") {
                          navigation.navigate("AdminHome");
                        } else {
                          goToApp();
                        }
                      }}
                    />
                    <View style={styles.content}>
                      <Screen />
                    </View>
                  </View>
                );
              }}
            </Stack.Screen>
          ))}
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
          goToApp();
        }}
        onLogout={() => {
          closeDrawer();
          void logout();
        }}
      />
    </View>
  );
}

const styles = lazyStyles(() => StyleSheet.create({
  shell: {
    flex: 1,
    backgroundColor: colors.background,
  },
  content: {
    flex: 1,
  },
}));
