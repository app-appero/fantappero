import * as Google from "expo-auth-session/providers/google";
import { useEffect } from "react";
import { Platform } from "react-native";
import { loadMobileEnv } from "../config/env";

export type GoogleAuthState = {
  /** False when no Google Web Client ID is configured — hide the button. */
  available: boolean;
  promptAsync: () => Promise<void>;
};

/**
 * Expo's Google hook throws on Android when `androidClientId` is missing.
 * The ids in `.env` are optional, so a placeholder keeps the hook mounted
 * and the button stays hidden until both client ids are set.
 */
const UNCONFIGURED_GOOGLE_CLIENT_ID = "unconfigured";

/**
 * Wraps expo-auth-session's Google provider (deprecated upstream in favor of
 * native Sign-In modules, but still shipped and sufficient for the Fase 1
 * web+Android pilot without adding a native dependency).
 */
export function useGoogleAuth(onIdToken: (idToken: string) => void): GoogleAuthState {
  const env = loadMobileEnv();
  const webClientId = env.expoPublicGoogleClientIdWeb;
  const androidClientId = env.expoPublicGoogleClientIdAndroid;
  const configured =
    Boolean(webClientId) && (Platform.OS !== "android" || Boolean(androidClientId));
  const [request, response, promptAsync] = Google.useIdTokenAuthRequest({
    webClientId: webClientId || UNCONFIGURED_GOOGLE_CLIENT_ID,
    androidClientId: androidClientId || UNCONFIGURED_GOOGLE_CLIENT_ID,
    iosClientId: UNCONFIGURED_GOOGLE_CLIENT_ID,
  });

  useEffect(() => {
    if (!configured) {
      return;
    }
    if (response?.type === "success" && response.params.id_token) {
      onIdToken(response.params.id_token);
    }
  }, [configured, response, onIdToken]);

  if (!configured) {
    return {
      available: false,
      promptAsync: async () => {},
    };
  }

  return {
    available: request !== null,
    promptAsync: async () => {
      await promptAsync();
    },
  };
}
