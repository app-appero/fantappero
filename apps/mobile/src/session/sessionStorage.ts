import { Platform } from "react-native";
import * as SecureStore from "expo-secure-store";
import type { SessionUser } from "@fantappero/contracts";

const ACCESS_TOKEN_KEY = "fantappero.accessToken";
const REFRESH_TOKEN_KEY = "fantappero.refreshToken";
const USER_KEY = "fantappero.sessionUser";
const ACTIVE_LEAGUE_ID_KEY = "fantappero.activeLeagueId";

export type StoredSession = {
  accessToken: string;
  refreshToken: string;
  user: SessionUser;
};

/**
 * Persistenza sessione: Keychain/Keystore via `expo-secure-store` su iOS/Android,
 * così la sessione sopravvive alla chiusura completa dell'app (era solo in
 * memoria, vedi matrice di parità C1 — problema #2). Su web (`expo start --web`,
 * solo per sviluppo: la web app reale è `apps/web`, un progetto separato)
 * SecureStore non è disponibile, si usa `localStorage` come fallback.
 */
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

async function deleteItem(key: string): Promise<void> {
  if (Platform.OS === "web") {
    if (typeof localStorage !== "undefined") {
      localStorage.removeItem(key);
    }
    return;
  }
  await SecureStore.deleteItemAsync(key);
}

let memorySession: StoredSession | null = null;

export function getMemorySession(): StoredSession | null {
  return memorySession;
}

export function setMemorySession(session: StoredSession | null): void {
  memorySession = session;
}

export async function loadStoredSession(): Promise<StoredSession | null> {
  const [accessToken, refreshToken, userRaw] = await Promise.all([
    getItem(ACCESS_TOKEN_KEY),
    getItem(REFRESH_TOKEN_KEY),
    getItem(USER_KEY),
  ]);
  if (!accessToken || !refreshToken || !userRaw) {
    return memorySession;
  }
  try {
    const session: StoredSession = {
      accessToken,
      refreshToken,
      user: JSON.parse(userRaw) as SessionUser,
    };
    memorySession = session;
    return session;
  } catch {
    await clearStoredSession();
    return null;
  }
}

export async function saveStoredSession(session: StoredSession): Promise<void> {
  await Promise.all([
    setItem(ACCESS_TOKEN_KEY, session.accessToken),
    setItem(REFRESH_TOKEN_KEY, session.refreshToken),
    setItem(USER_KEY, JSON.stringify(session.user)),
  ]);
  memorySession = session;
}

export async function clearStoredSession(): Promise<void> {
  await Promise.all([
    deleteItem(ACCESS_TOKEN_KEY),
    deleteItem(REFRESH_TOKEN_KEY),
    deleteItem(USER_KEY),
    deleteItem(ACTIVE_LEAGUE_ID_KEY),
  ]);
  memorySession = null;
}

export async function loadStoredActiveLeagueId(): Promise<string | null> {
  return getItem(ACTIVE_LEAGUE_ID_KEY);
}

export async function saveStoredActiveLeagueId(leagueId: string): Promise<void> {
  await setItem(ACTIVE_LEAGUE_ID_KEY, leagueId);
}

export async function clearStoredActiveLeagueId(): Promise<void> {
  await deleteItem(ACTIVE_LEAGUE_ID_KEY);
}
