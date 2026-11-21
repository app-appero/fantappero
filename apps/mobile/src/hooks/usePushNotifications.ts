import type { PushDevicePlatform } from "@fantappero/contracts";
import { useNavigation, type NavigationProp } from "@react-navigation/core";
import Constants, { ExecutionEnvironment } from "expo-constants";
import * as Device from "expo-device";
import type * as NotificationsModule from "expo-notifications";
import { useEffect, useRef } from "react";
import { Platform } from "react-native";
import { registerPushDevice } from "../api/notifications";
import { openAdminScreen } from "../navigation/adminEntry";
import { planNotificationOpen } from "../navigation/notificationDestination";
import type { RootStackParamList } from "../navigation/types";
import { useAuthSession } from "../session/DemoSessionContext";
import { pushNotificationsAvailable } from "./pushSupport";

type Notifications = typeof NotificationsModule;

/**
 * `expo-notifications` richiede un modulo nativo che Expo Go non ha: importarlo
 * a livello di file manderebbe in crash tutta l'app. Lo carichiamo solo in una
 * build vera (APK/dev client); in Expo Go e nel browser le push restano
 * semplicemente spente (vedi `pushNotificationsAvailable`).
 */
let cached: Notifications | null | undefined;
function loadNotifications(): Notifications | null {
  if (cached !== undefined) {
    return cached;
  }
  if (
    !pushNotificationsAvailable(
      Platform.OS,
      Constants.executionEnvironment === ExecutionEnvironment.StoreClient,
    )
  ) {
    cached = null;
    return cached;
  }
  try {
    // eslint-disable-next-line @typescript-eslint/no-require-imports
    const module = require("expo-notifications") as Notifications;
    module.setNotificationHandler({
      handleNotification: async () => ({
        shouldShowBanner: true,
        shouldShowList: true,
        shouldPlaySound: true,
        shouldSetBadge: false,
      }),
    });
    cached = module;
  } catch {
    cached = null;
  }
  return cached;
}

/**
 * Ricordati per tutta la vita del processo, non del componente: al cambio tema
 * la navigazione si rimonta (App.tsx) e con dei `useRef` l'hook ripartirebbe da
 * zero, riaprendo la notifica che ha aperto l'app, richiedendo di nuovo il
 * permesso a chi l'ha appena negato e registrando di nuovo il token.
 */
let registeredForToken: string | null = null;
let lastHandledResponseId: string | null = null;
let permissionAsked = false;

function platformName(): PushDevicePlatform | null {
  if (Platform.OS === "ios") return "ios";
  if (Platform.OS === "android") return "android";
  return null;
}

/**
 * Chiede il permesso, registra il token Expo del dispositivo quando c'è un
 * utente loggato, e naviga alla destinazione giusta quando l'utente tocca
 * una push — sia ad app aperta sia riaprendola da ferma (EP09-05).
 *
 * Richiede un progetto EAS collegato (`app.json` → `extra.eas.projectId`) e una
 * build vera: in Expo Go non fa nulla.
 */
export function usePushNotifications(accessToken: string | null | undefined): void {
  const navigation = useNavigation<NavigationProp<RootStackParamList>>();
  // Lega attiva e leghe di adesso, lette al tocco: l'ascoltatore resta registrato una volta
  // sola (dipende solo dalla navigazione) e non va rifatto a ogni cambio di lega.
  const { activeLeagueId, leagues, setActiveLeagueId } = useAuthSession();
  const leagueSessionRef = useRef({ activeLeagueId, leagues, setActiveLeagueId });
  leagueSessionRef.current = { activeLeagueId, leagues, setActiveLeagueId };

  useEffect(() => {
    const Notifications = loadNotifications();
    const platform = platformName();
    if (!accessToken || !Notifications || platform === null || !Device.isDevice) {
      return;
    }
    if (registeredForToken === accessToken) {
      return;
    }
    let cancelled = false;
    (async () => {
      const current = await Notifications.getPermissionsAsync();
      let granted = current.granted;
      // Al massimo una richiesta per avvio dell'app: col cambio tema non si ripropone.
      if (!granted && current.canAskAgain && !permissionAsked) {
        permissionAsked = true;
        granted = (await Notifications.requestPermissionsAsync()).granted;
      }
      const projectId = Constants.expoConfig?.extra?.eas?.projectId as string | undefined;
      if (!granted || cancelled || !projectId) {
        return;
      }
      try {
        const { data: token } = await Notifications.getExpoPushTokenAsync({ projectId });
        if (cancelled) {
          return;
        }
        await registerPushDevice(accessToken, { token, platform });
        registeredForToken = accessToken;
      } catch {
        // Offline o errore del provider push: si ritenta al prossimo avvio.
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [accessToken]);

  useEffect(() => {
    const Notifications = loadNotifications();
    if (!Notifications) {
      return;
    }
    function handle(response: NotificationsModule.NotificationResponse | null | undefined) {
      if (!response) {
        return;
      }
      const id = response.notification.request.identifier;
      if (lastHandledResponseId === id) {
        return;
      }
      lastHandledResponseId = id;
      const content = response.notification.request.content;
      const deepLink = (content.data?.deepLink as string | null | undefined) ?? null;
      const session = leagueSessionRef.current;
      const plan = planNotificationOpen({ title: content.title ?? "", deepLink }, session);
      if (!plan) {
        return;
      }
      // Il deep link della push porta `?lega=`: prima quella lega (se ne fa parte), poi la
      // schermata. Anche ad app riaperta da ferma: questa shell si monta a leghe già caricate.
      if (plan.switchToLeagueId) {
        session.setActiveLeagueId(plan.switchToLeagueId);
      }
      const { route } = plan;
      if (route.kind === "matchup") {
        (navigation as unknown as { navigate: (name: string, params: object) => void }).navigate("MatchupDetail", { slotId: route.slotId });
      } else if (route.kind === "stack") {
        (navigation as unknown as { navigate: (name: string, params?: object) => void }).navigate(route.name, route.params);
      } else if (route.kind === "tab") {
        navigation.navigate("MainTabs", { screen: route.screen, params: route.params });
      } else if (route.kind === "admin") {
        openAdminScreen(route.screen);
        navigation.navigate("AdminPanel");
      }
    }
    // App riaperta da ferma toccando la notifica, poi tocchi ad app viva.
    void Notifications.getLastNotificationResponseAsync().then(handle);
    const subscription = Notifications.addNotificationResponseReceivedListener(handle);
    return () => subscription.remove();
  }, [navigation]);
}
