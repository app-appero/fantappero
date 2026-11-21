import * as SecureStore from "expo-secure-store";
import { Platform } from "react-native";
import { parseDismissedVersionCode } from "./updateBanner";

/** versionCode per cui si è toccato «Più tardi» (stesso archivio della preferenza del tema). */
const DISMISSED_VERSION_KEY = "fantappero.appUpdateDismissedCode";

export async function loadDismissedVersionCode(): Promise<number | null> {
  if (Platform.OS === "web") {
    return null;
  }
  return parseDismissedVersionCode(await SecureStore.getItemAsync(DISMISSED_VERSION_KEY));
}

export async function saveDismissedVersionCode(code: number): Promise<void> {
  if (Platform.OS === "web") {
    return;
  }
  await SecureStore.setItemAsync(DISMISSED_VERSION_KEY, String(code));
}
