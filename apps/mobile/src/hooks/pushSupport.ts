/**
 * Le notifiche push esistono solo in una build vera per Android o iOS.
 *
 * - In Expo Go manca il modulo nativo di `expo-notifications`.
 * - Nel browser (`expo start --web`, solo per sviluppo: il sito vero è `apps/web`)
 *   `getLastNotificationResponseAsync` non esiste e a ogni avvio con una sessione aperta
 *   lanciava in console «UnavailabilityError: The method or property
 *   ExpoNotifications.getLastNotificationResponse is not available on web», più tre avvisi
 *   «not yet fully supported on web» (QA 20-21/11). Sul web il modulo non si carica affatto.
 */
export function pushNotificationsAvailable(platformOS: string, isExpoGo: boolean): boolean {
  return !isExpoGo && (platformOS === "android" || platformOS === "ios");
}
