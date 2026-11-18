import { BarlowCondensed_800ExtraBold_Italic } from "@expo-google-fonts/barlow-condensed";
import { theme } from "@fantappero/ui/theme";
import { NavigationContainer, createNavigationContainerRef } from "@react-navigation/native";
import { useFonts } from "expo-font";
import { StatusBar } from "expo-status-bar";
import { View } from "react-native";
import { GlobalListoneRefreshBar, ListoneRefreshProvider } from "./src/admin/ListoneRefreshContext";
import { AthleteCardProvider } from "./src/athletes/AthleteCard";
import { AppErrorBoundary } from "./src/errors/AppErrorBoundary";
import { AppLinkHandler } from "./src/navigation/AppLinkHandler";
import { RootNavigator } from "./src/navigation/RootNavigator";
import type { RootStackParamList } from "./src/navigation/types";
import { DemoSessionProvider } from "./src/session/DemoSessionContext";
import { AppThemeProvider, useAppTheme } from "./src/theme/AppTheme";
import { buildNavigationTheme } from "./src/theme/navigationTheme";

const { colors } = theme;
const navigationRef = createNavigationContainerRef<RootStackParamList>();

function ThemedShell() {
  const { scheme } = useAppTheme();
  return (
    <DemoSessionProvider>
      <AthleteCardProvider>
      <ListoneRefreshProvider>
        <View style={{ flex: 1, backgroundColor: colors.background }}>
          <NavigationContainer ref={navigationRef} theme={buildNavigationTheme()}>
            <StatusBar style={scheme === "dark" ? "light" : "dark"} />
            <AppErrorBoundary>
              <RootNavigator />
            </AppErrorBoundary>
            <AppLinkHandler navigationRef={navigationRef} />
          </NavigationContainer>
          <GlobalListoneRefreshBar />
        </View>
      </ListoneRefreshProvider>
      </AthleteCardProvider>
    </DemoSessionProvider>
  );
}

export default function App() {
  // I font si caricano in background: finché non sono pronti vale il font di sistema.
  useFonts({ BarlowCondensed_800ExtraBold_Italic });
  return (
    <AppThemeProvider>
      <ThemedShell />
    </AppThemeProvider>
  );
}
