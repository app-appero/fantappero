import type { LeagueSummary, SessionUser } from "@fantappero/contracts";

const ACCESS_TOKEN_KEY = "fantappero.accessToken";
const REFRESH_TOKEN_KEY = "fantappero.refreshToken";
const USER_KEY = "fantappero.sessionUser";
const ACTIVE_LEAGUE_ID_KEY = "fantappero.activeLeagueId";
const MY_LEAGUES_KEY = "fantappero.myLeagues";
// Sessione dell'operatore messa da parte mentre impersona un altro utente a
// scopo di assistenza: permette di tornare al proprio account senza rifare
// login (EP11-impersonation).
const IMPERSONATOR_SESSION_KEY = "fantappero.impersonatorSession";

type StoredMyLeagues = {
  userId: string;
  leagues: LeagueSummary[];
};

function isLeagueSummary(value: unknown): value is LeagueSummary {
  if (!value || typeof value !== "object") {
    return false;
  }
  const row = value as Record<string, unknown>;
  return (
    typeof row.id === "string" &&
    typeof row.name === "string" &&
    typeof row.role === "string" &&
    typeof row.state === "string"
  );
}

export type StoredSession = {
  accessToken: string;
  refreshToken: string;
  user: SessionUser;
};

export function loadStoredSession(): StoredSession | null {
  if (typeof localStorage === "undefined") {
    return null;
  }
  const accessToken = localStorage.getItem(ACCESS_TOKEN_KEY);
  const refreshToken = localStorage.getItem(REFRESH_TOKEN_KEY);
  const userRaw = localStorage.getItem(USER_KEY);
  // `refreshToken` può essere stringa vuota per una sessione di
  // impersonificazione (nessun refresh token emesso di proposito): solo
  // `null` (chiave assente) indica che non c'è una sessione salvata.
  if (!accessToken || refreshToken === null || !userRaw) {
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
  localStorage.setItem(ACCESS_TOKEN_KEY, session.accessToken);
  localStorage.setItem(REFRESH_TOKEN_KEY, session.refreshToken);
  localStorage.setItem(USER_KEY, JSON.stringify(session.user));
}

export function clearStoredSession(): void {
  localStorage.removeItem(ACCESS_TOKEN_KEY);
  localStorage.removeItem(REFRESH_TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
  localStorage.removeItem(ACTIVE_LEAGUE_ID_KEY);
  localStorage.removeItem(MY_LEAGUES_KEY);
  // Un logout o una sessione non più valida chiude anche un'eventuale
  // impersonificazione in corso: non deve restare un account "in pausa" da
  // ripristinare dopo un login successivo non correlato.
  localStorage.removeItem(IMPERSONATOR_SESSION_KEY);
}

/** Sessione dell'operatore accantonata mentre impersona un altro utente, `null` se non in corso. */
export function loadImpersonatorSession(): StoredSession | null {
  if (typeof localStorage === "undefined") {
    return null;
  }
  const raw = localStorage.getItem(IMPERSONATOR_SESSION_KEY);
  if (!raw) {
    return null;
  }
  try {
    return JSON.parse(raw) as StoredSession;
  } catch {
    localStorage.removeItem(IMPERSONATOR_SESSION_KEY);
    return null;
  }
}

export function saveImpersonatorSession(session: StoredSession): void {
  localStorage.setItem(IMPERSONATOR_SESSION_KEY, JSON.stringify(session));
}

export function clearImpersonatorSession(): void {
  localStorage.removeItem(IMPERSONATOR_SESSION_KEY);
}

export function loadStoredActiveLeagueId(): string | null {
  if (typeof localStorage === "undefined") {
    return null;
  }
  return localStorage.getItem(ACTIVE_LEAGUE_ID_KEY);
}

export function saveStoredActiveLeagueId(leagueId: string): void {
  localStorage.setItem(ACTIVE_LEAGUE_ID_KEY, leagueId);
}

export function clearStoredActiveLeagueId(): void {
  localStorage.removeItem(ACTIVE_LEAGUE_ID_KEY);
}

export function loadStoredMyLeagues(userId: string | null): LeagueSummary[] {
  if (!userId || typeof localStorage === "undefined") {
    return [];
  }
  const raw = localStorage.getItem(MY_LEAGUES_KEY);
  if (!raw) {
    return [];
  }
  try {
    const parsed = JSON.parse(raw) as StoredMyLeagues;
    if (parsed.userId !== userId || !Array.isArray(parsed.leagues)) {
      return [];
    }
    return parsed.leagues.filter(isLeagueSummary);
  } catch {
    localStorage.removeItem(MY_LEAGUES_KEY);
    return [];
  }
}

export function saveStoredMyLeagues(userId: string, leagues: readonly LeagueSummary[]): void {
  localStorage.setItem(
    MY_LEAGUES_KEY,
    JSON.stringify({ userId, leagues: [...leagues] } satisfies StoredMyLeagues),
  );
}

export function clearStoredMyLeagues(): void {
  localStorage.removeItem(MY_LEAGUES_KEY);
}
