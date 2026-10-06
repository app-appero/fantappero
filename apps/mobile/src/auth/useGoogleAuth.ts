import * as Linking from "expo-linking";
import { useCallback, useEffect, useRef } from "react";
import { loadMobileEnv } from "../config/env";
import { claimGoogleIdToken, releaseGoogleIdToken } from "./googleAppHandoff";

export type GoogleAuthState = {
  /** False when the web client id or the site that hosts the Google button is missing. */
  available: boolean;
  promptAsync: () => Promise<void>;
};

/**
 * Opens the website Google button in the system browser and finishes when the
 * site returns an app URL that carries the ID token. An in-app tab blocks the
 * Google window, so the login has to stay in the full browser.
 */
export function useGoogleAuth(
  onIdToken: (idToken: string) => void | Promise<void>,
): GoogleAuthState {
  const env = loadMobileEnv();
  const clientId = env.expoPublicGoogleClientIdWeb;
  const webBaseUrl = env.expoPublicWebBaseUrl;
  const available = Boolean(clientId && webBaseUrl);
  const onIdTokenRef = useRef(onIdToken);
  onIdTokenRef.current = onIdToken;
  const claimRef = useRef({ token: null as string | null });

  useEffect(() => {
    if (!available) {
      return;
    }

    let cancelled = false;

    async function deliver(url: string | null) {
      if (cancelled) {
        return;
      }
      const idToken = claimGoogleIdToken(url, claimRef.current);
      if (!idToken) {
        return;
      }
      try {
        await onIdTokenRef.current(idToken);
      } finally {
        releaseGoogleIdToken(idToken, claimRef.current);
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
