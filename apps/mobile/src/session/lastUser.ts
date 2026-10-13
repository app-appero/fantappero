import { Platform } from "react-native";
import * as SecureStore from "expo-secure-store";

/** Ultimo account che ha fatto accesso su questo dispositivo (nome ed email, nessun segreto). */

const LAST_USER_KEY = "fantappero.lastUser";

export type LastUser = {
  displayName: string;
  email: string;
};

async function getItem(key: string): Promise<string | null> {
  if (Platform.OS === "web") {
    return typeof localStorage === "undefined" ? null : localStorage.getItem(key);
  }
  return SecureStore.getItemAsync(key);
}

export async function readLastUser(): Promise<LastUser | null> {
  try {
    const raw = await getItem(LAST_USER_KEY);
    if (!raw) {
      return null;
    }
    const parsed = JSON.parse(raw) as Partial<LastUser> | null;
    if (parsed && typeof parsed.displayName === "string" && typeof parsed.email === "string" && parsed.displayName.trim() && parsed.email.trim()) {
      return { displayName: parsed.displayName, email: parsed.email };
    }
  } catch {
    // dati rovinati: modulo normale
  }
  return null;
}

export async function writeLastUser(user: LastUser): Promise<void> {
  try {
    const value = JSON.stringify(user);
    if (Platform.OS === "web") {
      if (typeof localStorage !== "undefined") localStorage.setItem(LAST_USER_KEY, value);
      return;
    }
    await SecureStore.setItemAsync(LAST_USER_KEY, value);
  } catch {
    // solo una comodità
  }
}

export async function clearLastUser(): Promise<void> {
  try {
    if (Platform.OS === "web") {
      if (typeof localStorage !== "undefined") localStorage.removeItem(LAST_USER_KEY);
      return;
    }
    await SecureStore.deleteItemAsync(LAST_USER_KEY);
  } catch {
    // vedi sopra
  }
}

export function initialsOf(displayName: string): string {
  const parts = displayName.trim().split(/\s+/).filter(Boolean);
  const letters = parts.length > 1 ? [parts[0], parts[parts.length - 1]] : [parts[0] ?? "?"];
  return letters.map((p) => p?.charAt(0) ?? "").join("").toUpperCase().slice(0, 2);
}
