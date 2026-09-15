/**
 * Typed public environment for the web client (EP01-04).
 * Only VITE_* variables are bundled — never put secrets here.
 */

export type WebEnv = {
  viteApiBaseUrl: string;
};

export class WebEnvError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "WebEnvError";
  }
}

function parseUrl(name: string, value: string): string {
  try {
    const parsed = new URL(value);
    return parsed.toString().replace(/\/$/, "") || parsed.origin;
  } catch {
    throw new WebEnvError(`Malformed ${name}: must be a valid URL`);
  }
}

let cachedEnv: WebEnv | null = null;

export function loadWebEnv(
  source: Record<string, string | boolean | undefined> = import.meta.env,
): WebEnv {
  const raw = source.VITE_API_BASE_URL;
  const text = typeof raw === "string" ? raw.trim() : "";
  if (!text) {
    throw new WebEnvError("Missing required environment variable: VITE_API_BASE_URL");
  }
  return { viteApiBaseUrl: parseUrl("VITE_API_BASE_URL", text) };
}

export function getWebEnv(): WebEnv {
  if (cachedEnv === null) {
    cachedEnv = loadWebEnv();
  }
  return cachedEnv;
}

export function resetWebEnvCache(): void {
  cachedEnv = null;
}

function isLoopbackHostname(hostname: string): boolean {
  return hostname === "localhost" || hostname === "127.0.0.1" || hostname === "[::1]" || hostname === "::1";
}

/**
 * The browser must not call loopback when the UI is served from another host
 * (LAN IP, Railway preview, …): that would hit the user's own machine.
 */
export function resolveApiBaseUrl(
  configured: string,
  pageHref: string | undefined = typeof window === "undefined" ? undefined : window.location.href,
): string {
  if (!pageHref) {
    return configured;
  }
  let configuredHost: string;
  try {
    configuredHost = new URL(configured).hostname;
  } catch {
    return configured;
  }
  if (!isLoopbackHostname(configuredHost)) {
    return configured;
  }
  let pageUrl: URL;
  try {
    pageUrl = new URL(pageHref);
  } catch {
    return configured;
  }
  if (isLoopbackHostname(pageUrl.hostname)) {
    return configured;
  }
  return pageUrl.origin;
}
