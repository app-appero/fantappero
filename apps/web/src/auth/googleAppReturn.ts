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

/**
 * Browser redirect that hands the one-time pickup code back to the app.
 *
 * Carries `code`, never a usable token: `fantappero://` has no verified Android App Link /
 * iOS Universal Link domain, so another app on the phone could in principle register the same
 * scheme and intercept this link. A single-use, short-lived code limits what that would buy
 * them (see `auth.mobile_handoff` on the backend).
 */
export function googleAppHandoffUrl(returnUrl: string, code: string): string {
  const url = new URL(returnUrl);
  url.searchParams.set("code", code);
  return url.toString();
}
