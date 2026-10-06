import * as Linking from "expo-linking";
import * as WebBrowser from "expo-web-browser";
import { useCallback } from "react";
import { loadMobileEnv } from "../config/env";
import { readGoogleIdToken } from "./googleAppHandoff";

export type GoogleAuthState = {
  /** False when the web client id or the site that hosts the Google button is missing. */
  available: boolean;
  promptAsync: () => Promise<void>;
};

WebBrowser.maybeCompleteAuthSession();

/**
 * Opens the website's Google button and receives the ID token through the app
 * scheme. The website origin is already allowed by Google; Expo Go cannot use
 * a custom redirect on the web client id.
 */
export function useGoogleAuth(onIdToken: (idToken: string) => void): GoogleAuthState {
  const env = loadMobileEnv();
  const clientId = env.expoPublicGoogleClientIdWeb;
  const webBaseUrl = env.expoPublicWebBaseUrl;
  const available = Boolean(clientId && webBaseUrl);

  const promptAsync = useCallback(async () => {
    if (!clientId || !webBaseUrl) {
      return;
    }
    const returnUrl = Linking.createURL("google-auth");
    const start = new URL("/accedi/google-app", webBaseUrl);
    start.searchParams.set("return", returnUrl);
    const result = await WebBrowser.openAuthSessionAsync(start.toString(), returnUrl);
    if (result.type !== "success") {
      return;
    }
    const idToken = readGoogleIdToken(result.url);
    if (!idToken) {
      throw new Error("Accesso con Google non riuscito.");
    }
    onIdToken(idToken);
  }, [clientId, onIdToken, webBaseUrl]);

  return { available, promptAsync };
}
