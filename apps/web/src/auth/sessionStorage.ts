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

export function loadStoredSession(): StoredSession | null {
  if (typeof sessionStorage === "undefined") {
    return null;
  }
  const accessToken = sessionStorage.getItem(ACCESS_TOKEN_KEY);
  const refreshToken = sessionStorage.getItem(REFRESH_TOKEN_KEY);
  const userRaw = sessionStorage.getItem(USER_KEY);
  if (!accessToken || !refreshToken || !userRaw) {
    return null;
  }
  try {
    return {
      accessToken,
      refreshToken,
      user: JSON.parse(userRaw) as SessionUser,
    };
  } catch {
    clearStoredSession();
    return null;
  }
}

export function saveStoredSession(session: StoredSession): void {
  sessionStorage.setItem(ACCESS_TOKEN_KEY, session.accessToken);
  sessionStorage.setItem(REFRESH_TOKEN_KEY, session.refreshToken);
  sessionStorage.setItem(USER_KEY, JSON.stringify(session.user));
}

export function clearStoredSession(): void {
  sessionStorage.removeItem(ACCESS_TOKEN_KEY);
  sessionStorage.removeItem(REFRESH_TOKEN_KEY);
  sessionStorage.removeItem(USER_KEY);
  sessionStorage.removeItem(ACTIVE_LEAGUE_ID_KEY);
}

export function loadStoredActiveLeagueId(): string | null {
  if (typeof sessionStorage === "undefined") {
    return null;
  }
  return sessionStorage.getItem(ACTIVE_LEAGUE_ID_KEY);
}

export function saveStoredActiveLeagueId(leagueId: string): void {
  sessionStorage.setItem(ACTIVE_LEAGUE_ID_KEY, leagueId);
}

export function clearStoredActiveLeagueId(): void {
  sessionStorage.removeItem(ACTIVE_LEAGUE_ID_KEY);
}
