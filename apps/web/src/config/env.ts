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

export function getApiBaseUrl(): string {
  return loadWebEnv().viteApiBaseUrl;
}
