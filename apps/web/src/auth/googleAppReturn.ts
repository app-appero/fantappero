const ALLOWED_APP_SCHEMES = new Set(["fantappero", "exp", "exps"]);

/** App return URL for the mobile Google handoff. Rejects web and script URLs. */
export function googleAppReturnUrl(raw: string | null | undefined): string | null {
  if (!raw?.trim()) {
    return null;
  }
  let url: URL;
  try {
    url = new URL(raw.trim());
  } catch {
    return null;
  }
  const scheme = url.protocol.replace(/:$/, "");
  if (!ALLOWED_APP_SCHEMES.has(scheme) || url.username || url.password) {
    return null;
  }
  return url.toString();
}

/** Browser redirect that hands the Google ID token back to the app. */
export function googleAppHandoffUrl(returnUrl: string, idToken: string): string {
  const url = new URL(returnUrl);
  url.searchParams.set("id_token", idToken);
  return url.toString();
}
