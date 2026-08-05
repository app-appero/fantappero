import { createNativeStackNavigator } from "@react-navigation/native-stack";
import { StyleSheet, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { theme } from "@fantappero/ui/theme";
import { AppHeader } from "../layout/AppHeader";
import { useDemoSession } from "../session/DemoSessionContext";
import { WireframePlaceholderScreen } from "../wireframes/WireframePlaceholderScreen";
import { MOBILE_ADMIN_NAV_ITEMS, NAV_LABELS } from "./navConfig";
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
  const { user } = useDemoSession();

  return (
    <View style={[styles.shell, { paddingTop: insets.top }]}>
      <AppHeader
        surface="admin"
        userDisplayName={user.displayName}
        onBrandPress={() => navigation.navigate("AdminPanel")}
        onBackToAppPress={() => navigation.navigate("MainTabs")}
        showDevSettings={__DEV__}
        onDevSettingsPress={() => navigation.navigate("DevSettings")}
      />
      <View style={styles.content}>{children}</View>
    </View>
  );
}

export function AdminNavigator() {
  return (
    <AdminShell>
      <Stack.Navigator screenOptions={{ headerShown: false, contentStyle: sceneBackgroundStyle }}>
        {MOBILE_ADMIN_NAV_ITEMS.map((item) => {
          const screenName =
            item.id === "admin-home"
              ? "AdminHome"
              : item.id === "admin-leagues"
                ? "AdminLeagues"
                : "AdminUsers";

          return (
            <Stack.Screen
              key={item.id}
              name={screenName}
              options={{ title: NAV_LABELS[item.id] }}
            >
              {() => <WireframePlaceholderScreen screenId="operator-panel" />}
            </Stack.Screen>
          );
        })}
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
