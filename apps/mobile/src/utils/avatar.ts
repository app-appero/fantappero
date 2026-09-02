import { loadMobileEnv, MobileEnvError } from "../config/env";

export function resolveAvatarUrl(avatarUrl: string | null): string | null {
  if (!avatarUrl) {
    return null;
  }
  if (avatarUrl.startsWith("http://") || avatarUrl.startsWith("https://")) {
    return avatarUrl;
  }
  try {
    return `${loadMobileEnv().expoPublicApiBaseUrl}${avatarUrl}`;
  } catch (error) {
    if (error instanceof MobileEnvError) {
      return null;
    }
    throw error;
  }
}
