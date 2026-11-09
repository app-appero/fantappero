import * as Linking from "expo-linking";
import { useCallback, useEffect, useRef } from "react";
import { loadMobileEnv } from "../config/env";
import { claimGoogleHandoffCode, releaseGoogleHandoffCode } from "./googleAppHandoff";

export type GoogleAuthState = {
  /** False when the web client id or the site that hosts the Google button is missing. */
  available: boolean;
  promptAsync: () => Promise<void>;
};

/**
 * Opens the website Google button in the system browser and finishes when the site returns an
 * app URL carrying a one-time pickup code (never the Google ID token or a usable session token
 * — see `googleAppHandoff.ts`). An in-app tab blocks the Google window, so the login has to
 * stay in the full browser.
 */
export function useGoogleAuth(onCode: (code: string) => void | Promise<void>): GoogleAuthState {
  const env = loadMobileEnv();
  const clientId = env.expoPublicGoogleClientIdWeb;
  const webBaseUrl = env.expoPublicWebBaseUrl;
  const available = Boolean(clientId && webBaseUrl);
  const onCodeRef = useRef(onCode);
  onCodeRef.current = onCode;
  const claimRef = useRef({ code: null as string | null });

  useEffect(() => {
    if (!available) {
      return;
    }

    let cancelled = false;

    async function deliver(url: string | null) {
      if (cancelled) {
        return;
      }
      const code = claimGoogleHandoffCode(url, claimRef.current);
      if (!code) {
        return;
      }
      try {
        await onCodeRef.current(code);
      } finally {
        releaseGoogleHandoffCode(code, claimRef.current);
      }
    }

    const subscription = Linking.addEventListener("url", (event) => {
      void deliver(event.url);
    });
    void Linking.getInitialURL().then((url) => deliver(url));

    return () => {
      cancelled = true;
      subscription.remove();
    };
  }, [available]);

  const promptAsync = useCallback(async () => {
    if (!clientId || !webBaseUrl) {
      return;
    }
    const returnUrl = Linking.createURL("google-auth");
    const start = new URL("/accedi/google-app", webBaseUrl);
    start.searchParams.set("return", returnUrl);
    await Linking.openURL(start.toString());
  }, [clientId, webBaseUrl]);

  return { available, promptAsync };
}
