/**
 * Intestazioni con la versione installata, aggiunte a ogni richiesta dell'app (release 1.4,
 * Rosario 23/11): il server registra chi ha quale versione (elenco «Versione app» del pannello
 * operatore) e non manda la notifica di una nuova versione a chi ce l'ha già.
 *
 * Solo logica pura: gira nei test `node:test`. I valori veri arrivano da `installedVersion.ts`.
 */
export const APP_VERSION_HEADER = "X-App-Version";
export const APP_VERSION_CODE_HEADER = "X-App-Version-Code";
export const APP_PLATFORM_HEADER = "X-App-Platform";

const VERSION_NAME = /^[0-9]+(\.[0-9]+){0,3}$/;

/**
 * `{ "X-App-Version": "1.4.0", "X-App-Version-Code": "5", "X-App-Platform": "android" }`.
 * Solo sull'APK Android e con un versionCode leggibile; altrimenti nessuna intestazione (il
 * server tratta la richiesta come prima).
 */
export function appVersionHeaders(
  platformOS: string,
  versionName: string | null | undefined,
  versionCode: number | null | undefined,
): Record<string, string> {
  if (platformOS !== "android") {
    return {};
  }
  if (typeof versionCode !== "number" || !Number.isSafeInteger(versionCode) || versionCode <= 0) {
    return {};
  }
  const headers: Record<string, string> = {
    [APP_VERSION_CODE_HEADER]: String(versionCode),
    [APP_PLATFORM_HEADER]: platformOS,
  };
  const name = (versionName ?? "").trim();
  if (VERSION_NAME.test(name)) {
    headers[APP_VERSION_HEADER] = name;
  }
  return headers;
}
