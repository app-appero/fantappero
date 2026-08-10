import { createBottomTabNavigator } from "@react-navigation/bottom-tabs";
import { useNavigation } from "@react-navigation/core";
import type { NativeStackNavigationProp } from "@react-navigation/native-stack";
import { useMemo, useState } from "react";
import { StyleSheet, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { theme } from "@fantappero/ui/theme";
import { AppDrawer } from "../components/AppDrawer";
import { AppHeader } from "../layout/AppHeader";
import { AuctionScreen } from "../screens/AuctionScreen";
import { LeaguesScreen } from "../screens/LeaguesScreen";
import { ProfileScreen } from "../screens/ProfileScreen";
import { useAuthSession } from "../session/DemoSessionContext";
import { WireframePlaceholderScreen } from "../wireframes/WireframePlaceholderScreen";
import {
  filterMobileNavItems,
  MOBILE_DRAWER_NAV_ITEMS,
  type ResolvedMobileNavItem,
} from "./navConfig";
import type { AppTabParamList, RootStackParamList } from "./types";
import { sceneBackgroundStyle } from "../theme/navigationTheme";

const Tab = createBottomTabNavigator<AppTabParamList>();
const { colors } = theme;

function MatchdayScreen() {
  return <WireframePlaceholderScreen screenId="matchday" />;
}
function StandingsScreen() {
  return <WireframePlaceholderScreen screenId="standings" />;
}
function RosterScreen() {
  return <WireframePlaceholderScreen screenId="roster" />;
}
function FormationScreen() {
  return <WireframePlaceholderScreen screenId="formation" />;
}
function MarketScreen() {
  return <WireframePlaceholderScreen screenId="market" />;
}

const TAB_ROUTE_MAP: Record<string, keyof AppTabParamList> = {
  leagues: "Leagues",
  matchday: "Matchday",
  standings: "Standings",
  roster: "Roster",
  formation: "Formation",
  auction: "Auction",
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
  Market: MarketScreen,
  Profile: ProfileScreen,
};

const ALL_TAB_IDS = [
  "leagues",
  "matchday",
  "standings",
  "roster",
  "formation",
  "auction",
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
  const { user, leagues, activeLeagueId, setActiveLeagueId, can, logout } = useAuthSession();
  const [drawerOpen, setDrawerOpen] = useState(false);

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
        onMenuPress={() => setDrawerOpen(true)}
        showLogout
        onLogoutPress={() => void handleLogout()}
        showLeagueSelector={leagues.length > 0}
        leagues={leagues.map((league) => ({ value: league.id, label: league.name }))}
        activeLeagueId={activeLeagueId}
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
