import { createBottomTabNavigator } from "@react-navigation/bottom-tabs";
import { useNavigation, useNavigationState } from "@react-navigation/core";
import type { NativeStackNavigationProp } from "@react-navigation/native-stack";
import { useCallback, useEffect, useMemo, useState } from "react";
import { StyleSheet, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { theme } from "@fantappero/ui/theme";
import { AppDrawer } from "../components/AppDrawer";
import { LockCountdown } from "../components/LockCountdown";
import { fetchPendingInviteCount } from "../api/managerInvites";
import { AppHeader } from "../layout/AppHeader";
import { useLockCountdown } from "../matchday/useLockCountdown";
import { AuctionScreen } from "../screens/AuctionScreen";
import { FormationScreen } from "../screens/FormationScreen";
import { LeaguesScreen } from "../screens/LeaguesScreen";
import { MarketScreen } from "../screens/MarketScreen";
import { MatchdayScreen } from "../screens/MatchdayScreen";
import { ProfileScreen } from "../screens/ProfileScreen";
import { RosterScreen } from "../screens/RosterScreen";
import { WaiverScreen } from "../screens/WaiverScreen";
import { StandingsScreen } from "../screens/StandingsScreen";
import { useAuthSession } from "../session/DemoSessionContext";
import {
  filterMobileNavItems,
  MOBILE_DRAWER_NAV_ITEMS,
  MOBILE_NAV_GROUPS,
  type ResolvedMobileNavItem,
} from "./navConfig";
import type { AppTabParamList, RootStackParamList } from "./types";
import { sceneBackgroundStyle } from "../theme/navigationTheme";

const Tab = createBottomTabNavigator<AppTabParamList>();
const { colors } = theme;

const TAB_ROUTE_MAP: Record<string, keyof AppTabParamList> = {
  leagues: "Leagues",
  matchday: "Matchday",
  standings: "Standings",
  roster: "Roster",
  formation: "Formation",
  auction: "Auction",
  waiver: "Waiver",
  market: "Market",
  profile: "Profile",
};

const STACK_ROUTE_MAP: Partial<Record<string, keyof RootStackParamList>> = {
  "league-home": "LeagueHome",
  "received-invites": "ReceivedInvites",
  "league-admin": "LeagueAdmin",
  "manager-directory": "ManagerDirectory",
};

const SCREEN_COMPONENTS: Record<keyof AppTabParamList, React.ComponentType> = {
  Leagues: LeaguesScreen,
  Matchday: MatchdayScreen,
  Standings: StandingsScreen,
  Roster: RosterScreen,
  Formation: FormationScreen,
  Auction: AuctionScreen,
  Waiver: WaiverScreen,
  Market: MarketScreen,
  Profile: ProfileScreen,
};

/** Route → id voce di menu, per evidenziare la destinazione corrente. */
const NAV_ID_BY_ROUTE: Record<string, string> = {
  ...Object.fromEntries(Object.entries(TAB_ROUTE_MAP).map(([id, route]) => [route, id])),
  ...Object.fromEntries(Object.entries(STACK_ROUTE_MAP).map(([id, route]) => [route, id])),
};

const ALL_TAB_IDS = [
  "leagues",
  "matchday",
  "standings",
  "roster",
  "formation",
  "auction",
  "waiver",
  "market",
  "profile",
] as const;

function AppTabShell({
  children,
  drawerItems,
}: {
  children: React.ReactNode;
  drawerItems: readonly ResolvedMobileNavItem[];
}) {
  const insets = useSafeAreaInsets();
  const navigation = useNavigation<NativeStackNavigationProp<RootStackParamList>>();
  const { user, leagues, activeLeagueId, setActiveLeagueId, can, logout, accessToken } =
    useAuthSession();
  const [drawerOpen, setDrawerOpen] = useState(false);
  // Stato aperto/chiuso conservato per la sessione: tutti i gruppi partono aperti.
  const [collapsedGroups, setCollapsedGroups] = useState<readonly string[]>([]);
  const [pendingInvites, setPendingInvites] = useState(0);

  // Nessun polling: si aggiorna all'apertura del drawer e dopo ogni azione
  // sugli inviti (EP13-P07).
  const refreshPendingInvites = useCallback(async () => {
    if (!accessToken) {
      setPendingInvites(0);
      return;
    }
    try {
      const result = await fetchPendingInviteCount(accessToken);
      setPendingInvites(result.pendingInviteCount);
    } catch {
      // Il badge è accessorio: un errore non deve rompere la navigazione.
      setPendingInvites(0);
    }
  }, [accessToken]);

  useEffect(() => {
    void refreshPendingInvites();
  }, [refreshPendingInvites]);

  const { countdown, refetch: refetchCountdown } = useLockCountdown(
    accessToken,
    leagues.length > 0 ? activeLeagueId : null,
  );

  const activeRouteName = useNavigationState((state) => {
    const route = state.routes[state.index];
    if (!route) {
      return undefined;
    }
    if (route.name !== "MainTabs") {
      return route.name;
    }
    const nested = route.state;
    if (nested && typeof nested.index === "number") {
      return nested.routes[nested.index]?.name;
    }
    // Stato annidato non ancora idratato: la tab iniziale è "Leagues".
    return "Leagues";
  });
  const activeItemId = activeRouteName ? (NAV_ID_BY_ROUTE[activeRouteName] ?? null) : null;

  const expandedGroupIds = MOBILE_NAV_GROUPS.filter(
    (group) => !collapsedGroups.includes(group.id),
  ).map((group) => group.id);

  function toggleGroup(groupId: string) {
    setCollapsedGroups((current) =>
      current.includes(groupId)
        ? current.filter((id) => id !== groupId)
        : [...current, groupId],
    );
  }

  function closeDrawer() {
    setDrawerOpen(false);
  }

  function handleDrawerNavigate(item: ResolvedMobileNavItem) {
    closeDrawer();
    const stackRoute = STACK_ROUTE_MAP[item.id];
    if (stackRoute) {
      navigation.navigate(stackRoute as never);
      return;
    }
    const tabRoute = TAB_ROUTE_MAP[item.id];
    if (tabRoute) {
      navigation.navigate("MainTabs", { screen: tabRoute } as never);
    }
  }

  async function handleLogout() {
    closeDrawer();
    await logout();
  }

  return (
    <View style={[styles.shell, { paddingTop: insets.top }]}>
      <AppHeader
        userDisplayName={user?.displayName ?? "Ospite"}
        showMenuButton
        onMenuPress={() => {
          // Il badge si aggiorna all'apertura del menu, senza polling.
          void refreshPendingInvites();
          setDrawerOpen(true);
        }}
        showLogout
        onLogoutPress={() => void handleLogout()}
        showLeagueSelector={leagues.length > 0}
        leagues={leagues.map((league) => ({ value: league.id, label: league.name }))}
        activeLeagueId={activeLeagueId}
        leagueSelectorAccessory={
          countdown ? (
            <LockCountdown
              state={countdown.state}
              nextLockAt={countdown.nextLockAt}
              onExpire={refetchCountdown}
            />
          ) : undefined
        }
        onLeagueChange={(leagueId) => {
          setActiveLeagueId(leagueId);
          navigation.navigate("LeagueHome", { leagueId });
        }}
        onBrandPress={() => navigation.navigate("MainTabs", { screen: "Leagues" } as never)}
      />
      <AppDrawer
        visible={drawerOpen}
        items={drawerItems}
        userDisplayName={user?.displayName ?? "Ospite"}
        showAdminPanel={can(["global:operate"])}
        activeItemId={activeItemId}
        expandedGroupIds={expandedGroupIds}
        onToggleGroup={toggleGroup}
        pendingInviteCount={pendingInvites}
        onNotificationsPress={() => {
          closeDrawer();
          navigation.navigate("Notifications");
        }}
        onClose={closeDrawer}
        onNavigate={handleDrawerNavigate}
        onAdminPanelPress={() => {
          closeDrawer();
          navigation.navigate("AdminPanel");
        }}
        onLogout={() => void handleLogout()}
      />
      <View style={styles.content}>{children}</View>
    </View>
  );
}

/** Navigazione solo via drawer: Tab navigator nascosto come router interno. */
export function AppTabNavigator() {
  const { can } = useAuthSession();
  const drawerItems = useMemo(
    () => filterMobileNavItems(MOBILE_DRAWER_NAV_ITEMS, can),
    [can],
  );

  return (
    <AppTabShell drawerItems={drawerItems}>
      <Tab.Navigator
        tabBar={() => null}
        screenOptions={{
          headerShown: false,
          sceneStyle: sceneBackgroundStyle,
        }}
      >
        {ALL_TAB_IDS.map((id) => {
          const routeName = TAB_ROUTE_MAP[id];
          if (!routeName) {
            return null;
          }
          return (
            <Tab.Screen
              key={id}
              name={routeName}
              component={SCREEN_COMPONENTS[routeName]}
            />
          );
        })}
      </Tab.Navigator>
    </AppTabShell>
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
