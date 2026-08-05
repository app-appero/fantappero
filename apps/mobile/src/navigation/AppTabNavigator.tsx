import { createBottomTabNavigator } from "@react-navigation/bottom-tabs";
import { useNavigation } from "@react-navigation/core";
import type { NativeStackNavigationProp } from "@react-navigation/native-stack";
import { useMemo } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { theme } from "@fantappero/ui/theme";
import { AppHeader } from "../layout/AppHeader";
import { AuctionScreen } from "../screens/AuctionScreen";
import { ProfileScreen } from "../screens/ProfileScreen";
import { useDemoSession } from "../session/DemoSessionContext";
import { WireframePlaceholderScreen } from "../wireframes/WireframePlaceholderScreen";
import { filterMobileNavItems, MOBILE_NAV_ITEMS, NAV_LABELS } from "./navConfig";
import type { AppTabParamList, RootStackParamList } from "./types";
import { sceneBackgroundStyle } from "../theme/navigationTheme";
import { NavIcon } from "./NavIcons";

const Tab = createBottomTabNavigator<AppTabParamList>();
const { colors, spacing, typography } = theme;

function LeaguesScreen() {
  const navigation = useNavigation<NativeStackNavigationProp<RootStackParamList>>();

  return (
    <View style={leaguesStyles.root}>
      <WireframePlaceholderScreen screenId="league-dashboard" />
      <Pressable
        accessibilityRole="button"
        accessibilityLabel="Crea lega"
        onPress={() => navigation.navigate("CreateLeague")}
        style={leaguesStyles.createButton}
        testID="mobile-leagues-create"
      >
        <Text style={leaguesStyles.createButtonLabel}>Crea lega</Text>
      </Pressable>
      <Pressable
        accessibilityRole="button"
        accessibilityLabel="Entra con un invito"
        onPress={() => navigation.navigate("JoinLeague")}
        style={leaguesStyles.joinButton}
        testID="mobile-leagues-join"
      >
        <Text style={leaguesStyles.joinButtonLabel}>Entra con un invito</Text>
      </Pressable>
      <Pressable
        accessibilityRole="button"
        accessibilityLabel="Inviti nominativi ricevuti"
        onPress={() => navigation.navigate("ReceivedInvites")}
        style={leaguesStyles.joinButton}
        testID="mobile-leagues-received-invites"
      >
        <Text style={leaguesStyles.joinButtonLabel}>Inviti ricevuti</Text>
      </Pressable>
    </View>
  );
}
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

function AppTabShell({ children }: { children: React.ReactNode }) {
  const insets = useSafeAreaInsets();
  const navigation = useNavigation<NativeStackNavigationProp<RootStackParamList>>();
  const { user, leagues, activeLeagueId, setActiveLeagueId, can } = useDemoSession();

  return (
    <View style={[styles.shell, { paddingTop: insets.top }]}>
      <AppHeader
        userDisplayName={user.displayName}
        showLeagueSelector={leagues.length > 0}
        leagues={leagues.map((league) => ({ value: league.id, label: league.name }))}
        activeLeagueId={activeLeagueId}
        onLeagueChange={setActiveLeagueId}
        onBrandPress={() => navigation.navigate("MainTabs", { screen: "Leagues" } as never)}
        showAdminLink={can(["global:operate"])}
        onAdminPress={() => navigation.navigate("AdminPanel")}
        showLeagueAdminLink={can(["league:admin"])}
        onLeagueAdminPress={() => navigation.navigate("LeagueAdmin")}
        showDevSettings={__DEV__}
        onDevSettingsPress={() => navigation.navigate("DevSettings")}
      />
      <View style={styles.content}>{children}</View>
    </View>
  );
}

export function AppTabNavigator() {
  const { can } = useDemoSession();
  const insets = useSafeAreaInsets();
  const visibleTabs = useMemo(() => filterMobileNavItems(MOBILE_NAV_ITEMS, can), [can]);

  return (
    <AppTabShell>
      <Tab.Navigator
        screenOptions={{
          headerShown: false,
          sceneStyle: sceneBackgroundStyle,
          tabBarStyle: [styles.tabBar, { paddingBottom: Math.max(insets.bottom, spacing.xs) }],
          tabBarActiveTintColor: colors.accent,
          tabBarInactiveTintColor: colors.foregroundMuted,
          tabBarLabelStyle: styles.tabLabel,
          tabBarItemStyle: styles.tabItem,
        }}
      >
        {visibleTabs.map((item) => {
          const routeName = TAB_ROUTE_MAP[item.id];
          if (!routeName) {
            return null;
          }
          return (
            <Tab.Screen
              key={item.id}
              name={routeName}
              component={SCREEN_COMPONENTS[routeName]}
              options={{
                tabBarAccessibilityLabel: item.label,
                tabBarIcon: ({ color, size }) => (
                  <NavIcon id={item.id} color={color} size={size} />
                ),
                tabBarLabel: ({ color }: { color: string }) => (
                  <Text
                    style={[styles.tabLabelText, { color }]}
                    numberOfLines={1}
                    testID={`mobile-tab-${item.id}`}
                  >
                    {NAV_LABELS[item.id]}
                  </Text>
                ),
              }}
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
  tabBar: {
    backgroundColor: colors.backgroundElevated,
    borderTopColor: colors.border,
    borderTopWidth: 1,
    paddingTop: spacing.xs,
  },
  tabItem: {
    minWidth: 72,
  },
  tabLabel: {
    fontSize: typography.fontSize.xs,
  },
  tabLabelText: {
    fontSize: typography.fontSize.xs,
  },
});

const leaguesStyles = StyleSheet.create({
  root: {
    flex: 1,
  },
  createButton: {
    margin: spacing.md,
    backgroundColor: colors.accent,
    borderRadius: 8,
    paddingVertical: spacing.md,
    alignItems: "center",
  },
  createButtonLabel: {
    color: colors.background,
    fontWeight: typography.fontWeight.semibold,
  },
  joinButton: {
    marginHorizontal: spacing.md,
    marginBottom: spacing.md,
    borderWidth: 1,
    borderColor: colors.accent,
    borderRadius: 8,
    paddingVertical: spacing.sm,
    alignItems: "center",
  },
  joinButtonLabel: {
    color: colors.accent,
    fontSize: typography.fontSize.sm,
    fontWeight: "600",
  },
});
