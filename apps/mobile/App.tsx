import { theme } from "@fantappero/ui/theme";
import { NavigationContainer } from "@react-navigation/native";
import { StatusBar } from "expo-status-bar";
import { View } from "react-native";
import { GlobalListoneRefreshBar, ListoneRefreshProvider } from "./src/admin/ListoneRefreshContext";
import { AthleteCardProvider } from "./src/athletes/AthleteCard";
import { AppErrorBoundary } from "./src/errors/AppErrorBoundary";
import { RootNavigator } from "./src/navigation/RootNavigator";
import { DemoSessionProvider } from "./src/session/DemoSessionContext";
import { AppThemeProvider, useAppTheme } from "./src/theme/AppTheme";
import { buildNavigationTheme } from "./src/theme/navigationTheme";

const { colors } = theme;

function ThemedShell() {
  const { scheme } = useAppTheme();
  return (
    <DemoSessionProvider>
      <AthleteCardProvider>
      <ListoneRefreshProvider>
        <View style={{ flex: 1, backgroundColor: colors.background }}>
          <NavigationContainer theme={buildNavigationTheme()}>
            <StatusBar style={scheme === "dark" ? "light" : "dark"} />
            <AppErrorBoundary>
              <RootNavigator />
            </AppErrorBoundary>
          </NavigationContainer>
          <GlobalListoneRefreshBar />
        </View>
      </ListoneRefreshProvider>
      </AthleteCardProvider>
    </DemoSessionProvider>
  );
}

export default function App() {
  return (
    <AppThemeProvider>
      <ThemedShell />
    </AppThemeProvider>
  );
}
