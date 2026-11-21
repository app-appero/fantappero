import Constants from "expo-constants";
import { appVersionLabel } from "./versionLabel";

/**
 * versionCode dell'app installata. Viene da `android.versionCode` di `app.json` (unica fonte:
 * il prebuild lo scrive nell'APK e expo-constants lo incorpora nella build); `null` se non si legge.
 */
export function installedAndroidVersionCode(): number | null {
  const code = Constants.expoConfig?.android?.versionCode;
  return typeof code === "number" && Number.isSafeInteger(code) && code > 0 ? code : null;
}

/**
 * Versione installata per le segnalazioni, es. «1.2.0 (3)»: `version` e `android.versionCode`
 * di `app.json`, letti come per l'avviso di nuova versione; `undefined` se non si leggono.
 */
export function installedAppVersionLabel(): string | undefined {
  return appVersionLabel(Constants.expoConfig?.version, installedAndroidVersionCode());
}
