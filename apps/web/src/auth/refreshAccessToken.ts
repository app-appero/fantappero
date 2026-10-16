import { ApiError } from "../api/client";
import * as authApi from "../api/auth";
import { accessTokenNeedsRefresh } from "./accessTokenExpiry";
import {
  clearImpersonatorSession,
  clearStoredSession,
  loadImpersonatorSession,
  loadStoredSession,
  saveStoredSession,
  type StoredSession,
} from "./sessionStorage";

let onChange: ((session: StoredSession | null) => void) | null = null;
let inFlight: Promise<string | null> | null = null;

export function setSessionChangeListener(
  listener: ((session: StoredSession | null) => void) | null,
): void {
  onChange = listener;
}

export function isTransientApiError(error: unknown): boolean {
  return (
    error instanceof ApiError &&
    (error.status === 0 || error.code === "network_error" || error.code === "invalid_response")
  );
}

export function refreshStoredSession(): Promise<string | null> {
  if (!inFlight) {
    inFlight = rotateStoredSession().finally(() => {
      inFlight = null;
    });
  }
  return inFlight;
}

export async function recoverAccessToken(failedAccessToken: string): Promise<string | null> {
  const current = loadStoredSession()?.accessToken;
  if (current && current !== failedAccessToken) {
    return current;
  }
  return refreshStoredSession();
}

export async function refreshSessionIfExpiring(): Promise<void> {
  const session = loadStoredSession();
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
  const session = loadStoredSession();
  if (!session) {
    return null;
  }
  if (!session.refreshToken) {
    const operator = loadImpersonatorSession();
    if (!operator?.accessToken) {
      return null;
    }
    clearImpersonatorSession();
    saveStoredSession(operator);
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
    saveStoredSession(next);
    onChange?.(next);
    return next.accessToken;
  } catch (error) {
    if (isTransientApiError(error)) {
      throw error;
    }
    clearStoredSession();
    onChange?.(null);
    return null;
  }
}
