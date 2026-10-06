/** Reads the ID token the web handoff page appended to the app return URL. */
export function readGoogleIdToken(url: string): string | null {
  try {
    const token = new URL(url).searchParams.get("id_token")?.trim() ?? "";
    return token || null;
  } catch {
    return null;
  }
}
