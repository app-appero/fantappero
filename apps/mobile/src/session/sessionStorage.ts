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
 * Persistenza sessione in-memory (processo app).
 * Con AsyncStorage installato in futuro si può sostituire il backend senza cambiare le API.
 */
const store = new Map<string, string>();

let memorySession: StoredSession | null = null;

export function getMemorySession(): StoredSession | null {
  return memorySession;
}

export function setMemorySession(session: StoredSession | null): void {
  memorySession = session;
}

export async function loadStoredSession(): Promise<StoredSession | null> {
  const accessToken = store.get(ACCESS_TOKEN_KEY) ?? null;
  const refreshToken = store.get(REFRESH_TOKEN_KEY) ?? null;
  const userRaw = store.get(USER_KEY) ?? null;
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
  store.set(ACCESS_TOKEN_KEY, session.accessToken);
  store.set(REFRESH_TOKEN_KEY, session.refreshToken);
  store.set(USER_KEY, JSON.stringify(session.user));
  memorySession = session;
}

export async function clearStoredSession(): Promise<void> {
  store.delete(ACCESS_TOKEN_KEY);
  store.delete(REFRESH_TOKEN_KEY);
  store.delete(USER_KEY);
  store.delete(ACTIVE_LEAGUE_ID_KEY);
  memorySession = null;
}

export async function loadStoredActiveLeagueId(): Promise<string | null> {
  return store.get(ACTIVE_LEAGUE_ID_KEY) ?? null;
}

export async function saveStoredActiveLeagueId(leagueId: string): Promise<void> {
  store.set(ACTIVE_LEAGUE_ID_KEY, leagueId);
}

export async function clearStoredActiveLeagueId(): Promise<void> {
  store.delete(ACTIVE_LEAGUE_ID_KEY);
}
