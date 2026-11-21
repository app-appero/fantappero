import { BarlowCondensed_800ExtraBold_Italic } from "@expo-google-fonts/barlow-condensed";
import {
  NavigationContainer,
  createNavigationContainerRef,
  type NavigationState,
} from "@react-navigation/native";
import { useFonts } from "expo-font";
import { StatusBar } from "expo-status-bar";
import { useRef } from "react";
import { View } from "react-native";
import { GlobalListoneRefreshBar, ListoneRefreshProvider } from "./src/admin/ListoneRefreshContext";
import { AthleteCardProvider } from "./src/athletes/AthleteCard";
import { AppErrorBoundary } from "./src/errors/AppErrorBoundary";
import { rememberLastScreen } from "./src/feedback/lastScreen";
import { AppLinkHandler } from "./src/navigation/AppLinkHandler";
import { focusedRouteName } from "./src/navigation/focusedRoute";
import { RootNavigator } from "./src/navigation/RootNavigator";
import type { RootStackParamList } from "./src/navigation/types";
import { DemoSessionProvider } from "./src/session/DemoSessionContext";
import { AppThemeProvider, useAppTheme } from "./src/theme/AppTheme";
import { buildNavigationTheme } from "./src/theme/navigationTheme";
import { statusBarStyleForBackground } from "./src/theme/statusBarStyle";

const navigationRef = createNavigationContainerRef<RootStackParamList>();

function ThemedShell() {
  const { scheme, resolvedColors } = useAppTheme();
  // Ultimo stato di navigazione visto: quando il tema cambia, la navigazione
  // riparte da qui e l'utente resta sulla stessa schermata (es. Profilo).
  const navigationState = useRef<NavigationState | undefined>(undefined);
  return (
    // Sessione, scheda calciatore e aggiornamento listone stanno sopra il
    // `key={scheme}` qui sotto: col cambio tema non si rimontano e non perdono
    // il loro stato (utente connesso, lega attiva, aggiornamento in corso).
    <DemoSessionProvider>
      <AthleteCardProvider>
      <ListoneRefreshProvider>
        <View style={{ flex: 1, backgroundColor: resolvedColors.background }}>
          {/* Icone scelte sul colore che sta davvero dietro la status bar. */}
          <StatusBar
            style={statusBarStyleForBackground(
              resolvedColors.background,
              scheme === "dark" ? "light" : "dark",
            )}
          />
          {/*
            Le schermate di React Navigation non si ridisegnano quando si
            ridisegna chi le contiene (ognuna è dietro un `StaticContainer`):
            i colori nuovi di `theme.colors` e di `lazyStyles` arriverebbero solo
            ai pochi componenti collegati al contesto del tema. Col `key` legato
            al tema l'intero albero di navigazione si rimonta al cambio e ogni
            schermata rilegge i colori nuovi; `initialState` la riporta dov'era.
          */}
          <NavigationContainer
            key={scheme}
            ref={navigationRef}
            theme={buildNavigationTheme()}
            initialState={navigationState.current}
            // «Segnala un problema» porta con sé la schermata a fuoco nell'intero albero
            // (tab, schermate dello stack come Home lega, pannello admin), qualunque sia la
            // strada per arrivarci. `onReady` copre la prima schermata, che non passa da
            // `onStateChange`; `getRootState` legge anche lo stato dei navigator annidati.
            onReady={() => {
              rememberLastScreen(focusedRouteName(navigationRef.getRootState()));
            }}
            onStateChange={(state) => {
              navigationState.current = state;
              rememberLastScreen(focusedRouteName(state));
            }}
          >
            <AppErrorBoundary>
              <RootNavigator />
            </AppErrorBoundary>
          </NavigationContainer>
          {/*
            Fuori dal `key`: rimontato rileggerebbe il link d'apertura dell'app
            (riaprendo la sua schermata) e perderebbe l'invito in attesa del login.
            Usa solo `navigationRef`, che segue il contenitore montato.
          */}
          <AppLinkHandler navigationRef={navigationRef} />
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
