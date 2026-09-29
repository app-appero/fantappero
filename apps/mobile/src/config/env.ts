/**
 * Typed public environment for the mobile client (EP01-04).
 * Only EXPO_PUBLIC_* variables are embedded — never put secrets here.
 */

export type MobileEnv = {
  expoPublicApiBaseUrl: string;
  /**
   * Google OAuth Web Client ID. Expo's Android auth flow still needs a "Web"
   * client (not just an Android one) to mint an id_token. Empty disables
   * the "Continua con Google" button.
   */
  expoPublicGoogleClientIdWeb: string;
  /** Google OAuth Android Client ID (package name + SHA-1), for EAS builds. */
  expoPublicGoogleClientIdAndroid: string;
};

export class MobileEnvError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "MobileEnvError";
  }
}

function parseUrl(name: string, value: string): string {
  try {
    const parsed = new URL(value);
    return parsed.toString().replace(/\/$/, "") || parsed.origin;
  } catch {
    throw new MobileEnvError(`Malformed ${name}: must be a valid URL`);
  }
}

export function loadMobileEnv(
  source: Record<string, string | undefined> = process.env as Record<string, string | undefined>,
): MobileEnv {
  const text = source.EXPO_PUBLIC_API_BASE_URL?.trim() ?? "";
  if (!text) {
    throw new MobileEnvError(
      "Missing required environment variable: EXPO_PUBLIC_API_BASE_URL",
    );
  }
  return {
    expoPublicApiBaseUrl: parseUrl("EXPO_PUBLIC_API_BASE_URL", text),
    expoPublicGoogleClientIdWeb: source.EXPO_PUBLIC_GOOGLE_CLIENT_ID_WEB?.trim() ?? "",
    expoPublicGoogleClientIdAndroid: source.EXPO_PUBLIC_GOOGLE_CLIENT_ID_ANDROID?.trim() ?? "",
  };
}
