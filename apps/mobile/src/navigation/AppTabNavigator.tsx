import { createBottomTabNavigator } from "@react-navigation/bottom-tabs";
import { useNavigation, useNavigationState } from "@react-navigation/core";
import type { NativeStackNavigationProp } from "@react-navigation/native-stack";
import { useCallback, useEffect, useMemo, useState } from "react";
import { StyleSheet, Text, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { theme } from "@fantappero/ui/theme";
import { AppDrawer } from "../components/AppDrawer";
import { LockCountdown } from "../components/LockCountdown";
import { fetchPendingInviteCount } from "../api/managerInvites";
import { AppHeader } from "../layout/AppHeader";
import { leagueStateLabel } from "../leagues/leagueLabels";
import { useLockCountdown } from "../matchday/useLockCountdown";
import { AuctionScreen } from "../screens/AuctionScreen";
import { FormationScreen } from "../screens/FormationScreen";
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
const { colors, spacing, typography, radius } = theme;

/** Drawer id → tab di destinazione quando l'id non è una sua stack route. */
const TAB_ROUTE_MAP: Partial<Record<string, keyof AppTabParamList>> = {
  matchday: "Matchday",
  standings: "Standings",
  // "Mercato" apre di default il tab Market; Rosa/Asta/Svincolati restano
  // raggiungibili dalla screen-tabs strip in cima a ciascuna schermata.
  "market-hub": "Market",
  formation: "Formation",
  profile: "Profile",
};

const STACK_ROUTE_MAP: Partial<Record<string, keyof RootStackParamList>> = {
  // "Lega" apre di default Home lega; Amministrazione resta raggiungibile
  // dalla screen-tabs strip in cima a Home lega/Amministrazione.
  "league-hub": "LeagueHome",
  "received-invites": "ReceivedInvites",
  "manager-directory": "ManagerDirectory",
};

const TAB_SCREEN_NAMES: (keyof AppTabParamList)[] = [
  "Matchday",
  "Standings",
  "Roster",
  "Formation",
  "Auction",
  "Waiver",
  "Market",
  "Profile",
];

const SCREEN_COMPONENTS: Record<keyof AppTabParamList, React.ComponentType> = {
  Matchday: MatchdayScreen,
  Standings: StandingsScreen,
  Roster: RosterScreen,
  Formation: FormationScreen,
  Auction: AuctionScreen,
  Waiver: WaiverScreen,
  Market: MarketScreen,
  Profile: ProfileScreen,
};

/** Route → id voce di menu, per evidenziare la destinazione corrente (più route → stesso hub). */
const NAV_ID_BY_ROUTE: Record<string, string> = {
  Matchday: "matchday",
  Standings: "standings",
  Roster: "market-hub",
  Formation: "formation",
  Auction: "market-hub",
  Waiver: "market-hub",
  Market: "market-hub",
  Profile: "profile",
  LeagueHome: "league-hub",
  LeagueAdmin: "league-hub",
  ReceivedInvites: "received-invites",
  ManagerDirectory: "manager-directory",
};

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

  const activeLeagueSummary = leagues.find(
    (league) => league.id === (activeLeagueId ?? leagues[0]?.id),
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
    // Stato annidato non ancora idratato: la tab iniziale è "Matchday".
    return "Matchday";
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
          <View style={styles.selectorAccessory}>
            {activeLeagueSummary ? (
              <View style={styles.statusBadge}>
                <Text style={styles.statusBadgeLabel}>
                  {leagueStateLabel(activeLeagueSummary.state)}
                </Text>
              </View>
            ) : null}
            {countdown ? (
              <LockCountdown
                state={countdown.state}
                nextLockAt={countdown.nextLockAt}
                onExpire={refetchCountdown}
              />
            ) : null}
          </View>
        }
        onLeagueChange={(leagueId) => {
          setActiveLeagueId(leagueId);
          navigation.navigate("LeagueHome", { leagueId });
        }}
        onCreateLeaguePress={() => navigation.navigate("CreateLeague")}
        onJoinLeaguePress={() => navigation.navigate("JoinLeague")}
        onBrandPress={() => navigation.navigate("LeagueHome")}
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
        {TAB_SCREEN_NAMES.map((routeName) => {
          return (
            <Tab.Screen
              key={routeName}
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
  selectorAccessory: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
  },
  statusBadge: {
    backgroundColor: colors.backgroundSubtle,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.sm,
    paddingHorizontal: spacing.xs,
    paddingVertical: 2,
  },
  statusBadgeLabel: {
    color: colors.foreground,
    fontSize: typography.fontSize.xs,
    fontWeight: typography.fontWeight.semibold,
  },
});
