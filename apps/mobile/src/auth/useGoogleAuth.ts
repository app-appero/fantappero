import * as Google from "expo-auth-session/providers/google";
import { useEffect } from "react";
import { loadMobileEnv } from "../config/env";

export type GoogleAuthState = {
  /** False when no Google Web Client ID is configured — hide the button. */
  available: boolean;
  promptAsync: () => Promise<void>;
};

/**
 * Wraps expo-auth-session's Google provider (deprecated upstream in favor of
 * native Sign-In modules, but still shipped and sufficient for the Fase 1
 * web+Android pilot without adding a native dependency).
 */
export function useGoogleAuth(onIdToken: (idToken: string) => void): GoogleAuthState {
  const env = loadMobileEnv();
  const [request, response, promptAsync] = Google.useIdTokenAuthRequest({
    webClientId: env.expoPublicGoogleClientIdWeb || undefined,
    androidClientId: env.expoPublicGoogleClientIdAndroid || undefined,
  });

  useEffect(() => {
    if (response?.type === "success" && response.params.id_token) {
      onIdToken(response.params.id_token);
    }
  }, [response, onIdToken]);

  return {
    available: Boolean(env.expoPublicGoogleClientIdWeb) && request !== null,
    promptAsync: async () => {
      await promptAsync();
    },
  };
}
