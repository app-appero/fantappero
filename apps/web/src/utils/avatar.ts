import { getWebEnv } from "../config/env";

export function resolveAvatarUrl(avatarUrl: string | null): string | null {
  if (!avatarUrl) {
    return null;
  }
  if (avatarUrl.startsWith("http://") || avatarUrl.startsWith("https://")) {
    return avatarUrl;
  }
  return `${getWebEnv().viteApiBaseUrl}${avatarUrl}`;
}
