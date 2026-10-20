import type { PushDevicePlatform } from "@fantappero/contracts";
import { useNavigation, type NavigationProp } from "@react-navigation/core";
import Constants, { ExecutionEnvironment } from "expo-constants";
import * as Device from "expo-device";
import type * as NotificationsModule from "expo-notifications";
import { useEffect, useRef } from "react";
import { Platform } from "react-native";
import { registerPushDevice } from "../api/notifications";
import { resolveNotificationRoute } from "../navigation/notificationDestination";
import type { RootStackParamList } from "../navigation/types";

type Notifications = typeof NotificationsModule;

/**
 * `expo-notifications` richiede un modulo nativo che Expo Go non ha: importarlo
 * a livello di file manderebbe in crash tutta l'app. Lo carichiamo solo in una
 * build vera (APK/dev client); in Expo Go le push restano semplicemente spente.
 */
let cached: Notifications | null | undefined;
function loadNotifications(): Notifications | null {
  if (cached !== undefined) {
    return cached;
  }
  if (Constants.executionEnvironment === ExecutionEnvironment.StoreClient) {
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
  const registeredForToken = useRef<string | null>(null);
  const lastHandledResponseId = useRef<string | null>(null);

  useEffect(() => {
    const Notifications = loadNotifications();
    const platform = platformName();
    if (!accessToken || !Notifications || platform === null || !Device.isDevice) {
      return;
    }
    if (registeredForToken.current === accessToken) {
      return;
    }
    let cancelled = false;
    (async () => {
      const current = await Notifications.getPermissionsAsync();
      let granted = current.granted;
      if (!granted && current.canAskAgain) {
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
        registeredForToken.current = accessToken;
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
      if (lastHandledResponseId.current === id) {
        return;
      }
      lastHandledResponseId.current = id;
      const content = response.notification.request.content;
      const deepLink = (content.data?.deepLink as string | null | undefined) ?? null;
      const route = resolveNotificationRoute({ title: content.title ?? "", deepLink });
      if (route?.kind === "stack") {
        navigation.navigate(route.name as never);
      } else if (route?.kind === "tab") {
        navigation.navigate("MainTabs", { screen: route.screen });
      }
    }
    // App riaperta da ferma toccando la notifica, poi tocchi ad app viva.
    void Notifications.getLastNotificationResponseAsync().then(handle);
    const subscription = Notifications.addNotificationResponseReceivedListener(handle);
    return () => subscription.remove();
  }, [navigation]);
}
