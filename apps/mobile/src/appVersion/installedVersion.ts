import Constants from "expo-constants";

/**
 * versionCode dell'app installata. Viene da `android.versionCode` di `app.json` (unica fonte:
 * il prebuild lo scrive nell'APK e expo-constants lo incorpora nella build); `null` se non si legge.
 */
export function installedAndroidVersionCode(): number | null {
  const code = Constants.expoConfig?.android?.versionCode;
  return typeof code === "number" && Number.isSafeInteger(code) && code > 0 ? code : null;
}
