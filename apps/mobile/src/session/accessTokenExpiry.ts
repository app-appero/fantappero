/** Reads the JWT `exp` claim without verifying the signature. Used only to refresh before expiry. */
export function accessTokenExpiresAtMs(token: string): number | null {
  const payload = token.split(".")[1];
  if (!payload) {
    return null;
  }
  try {
    const json = JSON.parse(decodeBase64Url(payload)) as { exp?: unknown };
    return typeof json.exp === "number" ? json.exp * 1000 : null;
  } catch {
    return null;
  }
}

/** True when the access token is missing, unreadable, or inside the skew window. */
export function accessTokenNeedsRefresh(token: string, now = Date.now(), skewMs = 120_000): boolean {
  const expiresAt = accessTokenExpiresAtMs(token);
  if (expiresAt == null) {
    return true;
  }
  return expiresAt - now <= skewMs;
}

function decodeBase64Url(input: string): string {
  const alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
  const value = input.replace(/-/g, "+").replace(/_/g, "/");
  let bits = 0;
  let buffer = 0;
  const bytes: number[] = [];
  for (const char of value) {
    if (char === "=") {
      break;
    }
    const index = alphabet.indexOf(char);
    if (index < 0) {
      continue;
    }
    buffer = (buffer << 6) | index;
    bits += 6;
    if (bits >= 8) {
      bits -= 8;
      bytes.push((buffer >> bits) & 0xff);
    }
  }
  return String.fromCharCode(...bytes);
}
