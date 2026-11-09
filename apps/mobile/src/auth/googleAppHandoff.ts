/**
 * Reads the one-time pickup code the web handoff page appended to the app return URL.
 *
 * Carries `code`, never the Google ID token or one of our own session tokens: the web page
 * already exchanged the ID token for a real session server-side, and this code is only how the
 * app claims it (`POST /auth/google/handoff/claim`). `fantappero://` has no verified Android
 * App Link / iOS Universal Link domain, so another app on the phone could in principle register
 * the same scheme and intercept this link; a single-use, short-lived code limits what that
 * would buy them.
 */
export function readGoogleHandoffCode(url: string): string | null {
  try {
    const code = new URL(url).searchParams.get("code")?.trim() ?? "";
    return code || null;
  } catch {
    return null;
  }
}

export type GoogleHandoffClaim = {
  code: string | null;
};

/**
 * Accepts one in-flight handoff for a code. A deep link and the initial URL
 * can both arrive for the same return; a later retry after release is allowed.
 */
export function claimGoogleHandoffCode(
  url: string | null,
  claim: GoogleHandoffClaim,
): string | null {
  if (!url) {
    return null;
  }
  const code = readGoogleHandoffCode(url);
  if (!code || claim.code === code) {
    return null;
  }
  claim.code = code;
  return code;
}

export function releaseGoogleHandoffCode(code: string, claim: GoogleHandoffClaim): void {
  if (claim.code === code) {
    claim.code = null;
  }
}
