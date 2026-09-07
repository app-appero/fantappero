import { NavigationContainer } from "@react-navigation/native";
import { StatusBar } from "expo-status-bar";
import { View } from "react-native";
import { GlobalListoneRefreshBar, ListoneRefreshProvider } from "./src/admin/ListoneRefreshContext";
import { AppErrorBoundary } from "./src/errors/AppErrorBoundary";
import { RootNavigator } from "./src/navigation/RootNavigator";
import { DemoSessionProvider } from "./src/session/DemoSessionContext";
import { appNavigationTheme } from "./src/theme/navigationTheme";

export default function App() {
  return (
    <DemoSessionProvider>
      <ListoneRefreshProvider>
        <View style={{ flex: 1 }}>
          <NavigationContainer theme={appNavigationTheme}>
            <StatusBar style="light" />
            <AppErrorBoundary>
              <RootNavigator />
            </AppErrorBoundary>
          </NavigationContainer>
          <GlobalListoneRefreshBar />
        </View>
      </ListoneRefreshProvider>
    </DemoSessionProvider>
  );
}
