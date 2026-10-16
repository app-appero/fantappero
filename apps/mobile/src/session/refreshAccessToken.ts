import { ApiError } from "../api/client";
import * as authApi from "../api/auth";
import { accessTokenNeedsRefresh } from "./accessTokenExpiry";
import {
  clearImpersonatorSession,
  clearStoredSession,
  getMemorySession,
  loadImpersonatorSession,
  loadStoredSession,
  saveStoredSession,
  type StoredSession,
} from "./sessionStorage";

export type SessionChange = StoredSession | null;

let onChange: ((session: SessionChange) => void) | null = null;
let inFlight: Promise<string | null> | null = null;

export function setSessionChangeListener(listener: ((session: SessionChange) => void) | null): void {
  onChange = listener;
}

export function isTransientApiError(error: unknown): boolean {
  return (
    error instanceof ApiError &&
    (error.status === 0 || error.code === "network_error" || error.code === "invalid_response")
  );
}

/** Renews the stored session once, even if several requests fail together. */
export function refreshStoredSession(): Promise<string | null> {
  if (!inFlight) {
    inFlight = rotateStoredSession().finally(() => {
      inFlight = null;
    });
  }
  return inFlight;
}

export async function recoverAccessToken(failedAccessToken: string): Promise<string | null> {
  const current = getMemorySession()?.accessToken;
  if (current && current !== failedAccessToken) {
    return current;
  }
  return refreshStoredSession();
}

/** Refreshes only when the access token is near expiry. A network blip keeps the session. */
export async function refreshSessionIfExpiring(): Promise<void> {
  const session = getMemorySession() ?? (await loadStoredSession());
  if (!session?.refreshToken || !accessTokenNeedsRefresh(session.accessToken)) {
    return;
  }
  try {
    await refreshStoredSession();
  } catch (error) {
    if (!isTransientApiError(error)) {
      throw error;
    }
  }
}

async function rotateStoredSession(): Promise<string | null> {
  const session = getMemorySession() ?? (await loadStoredSession());
  if (!session) {
    return null;
  }
  if (!session.refreshToken) {
    const operator = await loadImpersonatorSession();
    if (!operator?.accessToken) {
      return null;
    }
    await clearImpersonatorSession();
    await saveStoredSession(operator);
    onChange?.(operator);
    return operator.accessToken;
  }
  try {
    const refreshed = await authApi.refresh({ refreshToken: session.refreshToken });
    const next: StoredSession = {
      accessToken: refreshed.accessToken,
      refreshToken: refreshed.refreshToken,
      user: refreshed.user,
    };
    await saveStoredSession(next);
    onChange?.(next);
    return next.accessToken;
  } catch (error) {
    if (isTransientApiError(error)) {
      throw error;
    }
    await clearStoredSession();
    onChange?.(null);
    return null;
  }
}
