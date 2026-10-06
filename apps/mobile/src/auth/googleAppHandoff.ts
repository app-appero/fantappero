/** Reads the ID token the web handoff page appended to the app return URL. */
export function readGoogleIdToken(url: string): string | null {
  try {
    const token = new URL(url).searchParams.get("id_token")?.trim() ?? "";
    return token || null;
  } catch {
    return null;
  }
}

export type GoogleTokenClaim = {
  token: string | null;
};

/**
 * Accepts one in-flight handoff for a token. A deep link and the initial URL
 * can both arrive for the same return; a later retry after release is allowed.
 */
export function claimGoogleIdToken(url: string | null, claim: GoogleTokenClaim): string | null {
  if (!url) {
    return null;
  }
  const idToken = readGoogleIdToken(url);
  if (!idToken || claim.token === idToken) {
    return null;
  }
  claim.token = idToken;
  return idToken;
}

export function releaseGoogleIdToken(idToken: string, claim: GoogleTokenClaim): void {
  if (claim.token === idToken) {
    claim.token = null;
  }
}
