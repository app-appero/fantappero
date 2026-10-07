import { Platform } from "react-native";
import * as SecureStore from "expo-secure-store";
import { isThemePreference, type ThemePreference } from "./themePreference";

const THEME_PREFERENCE_KEY = "fantappero.colorScheme";

async function getItem(key: string): Promise<string | null> {
  if (Platform.OS === "web") {
    return typeof localStorage === "undefined" ? null : localStorage.getItem(key);
  }
  return SecureStore.getItemAsync(key);
}

async function setItem(key: string, value: string): Promise<void> {
  if (Platform.OS === "web") {
    if (typeof localStorage !== "undefined") {
      localStorage.setItem(key, value);
    }
    return;
  }
  await SecureStore.setItemAsync(key, value);
}

export async function loadThemePreference(): Promise<ThemePreference> {
  const stored = await getItem(THEME_PREFERENCE_KEY);
  return isThemePreference(stored) ? stored : "system";
}

export async function saveThemePreference(preference: ThemePreference): Promise<void> {
  await setItem(THEME_PREFERENCE_KEY, preference);
}
