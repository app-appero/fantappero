import type { PushDevicePlatform } from "@fantappero/contracts";
import { useNavigation, type NavigationProp } from "@react-navigation/core";
import Constants from "expo-constants";
import * as Device from "expo-device";
import * as Notifications from "expo-notifications";
import { useEffect, useRef } from "react";
import { Platform } from "react-native";
import { registerPushDevice } from "../api/notifications";
import { resolveNotificationRoute } from "../navigation/notificationDestination";
import type { RootStackParamList } from "../navigation/types";

// Mentre l'app è in primo piano una push arrivata si vede comunque, come se
// fosse in background — altrimenti su iOS sparirebbe senza che l'utente se
// ne accorga.
Notifications.setNotificationHandler({
  handleNotification: async () => ({
    shouldShowBanner: true,
    shouldShowList: true,
    shouldPlaySound: true,
    shouldSetBadge: false,
  }),
});

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
 * Richiede un progetto EAS collegato (`app.json` → `extra.eas.projectId`):
 * senza quello `getExpoPushTokenAsync` fallisce e la registrazione viene
 * saltata silenziosamente, l'app resta comunque utilizzabile.
 */
export function usePushNotifications(accessToken: string | null | undefined): void {
  const navigation = useNavigation<NavigationProp<RootStackParamList>>();
  const registeredForToken = useRef<string | null>(null);
  const lastHandledResponseId = useRef<string | null>(null);
  const response = Notifications.useLastNotificationResponse();

  useEffect(() => {
    if (!accessToken) {
      return;
    }
    const platform = platformName();
    if (platform === null) {
      return;
    }
    if (!Device.isDevice) {
      // Simulatore/emulatore: niente push reali, Expo rifiuterebbe comunque.
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
        const requested = await Notifications.requestPermissionsAsync();
        granted = requested.granted;
      }
      if (!granted || cancelled) {
        return;
      }
      const projectId = Constants.expoConfig?.extra?.eas?.projectId as string | undefined;
      if (!projectId) {
        // Nessun progetto EAS collegato: non possiamo ottenere un token Expo.
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
        // Offline o errore del provider push: non blocca l'app, si ritenta
        // al prossimo avvio o cambio di accessToken.
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [accessToken]);

  useEffect(() => {
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
  }, [response, navigation]);
}
