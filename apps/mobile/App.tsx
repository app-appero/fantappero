import { NavigationContainer } from "@react-navigation/native";
import { StatusBar } from "expo-status-bar";
import { AppErrorBoundary } from "./src/errors/AppErrorBoundary";
import { RootNavigator } from "./src/navigation/RootNavigator";
import { DemoSessionProvider } from "./src/session/DemoSessionContext";
import { appNavigationTheme } from "./src/theme/navigationTheme";

export default function App() {
  return (
    <DemoSessionProvider>
      <NavigationContainer theme={appNavigationTheme}>
        <StatusBar style="light" />
        <AppErrorBoundary>
          <RootNavigator />
        </AppErrorBoundary>
      </NavigationContainer>
    </DemoSessionProvider>
  );
}
