import { resolveColorScheme, type ThemePreference } from "@fantappero/ui/theme";

const STORAGE_KEY = "fantappero.colorScheme";

const listeners = new Set<() => void>();

export function isThemePreference(value: string | null): value is ThemePreference {
  return value === "light" || value === "dark" || value === "system";
}

export function readThemePreference(): ThemePreference {
  if (typeof localStorage === "undefined") {
    return "system";
  }
  const stored = localStorage.getItem(STORAGE_KEY);
  return isThemePreference(stored) ? stored : "system";
}

export function systemColorScheme(): "light" | "dark" | null {
  if (typeof window === "undefined" || typeof window.matchMedia !== "function") {
    return null;
  }
  return window.matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark";
}

/**
 * Colore della barra di stato dell'iPhone (app dalla schermata Home) e della barra del browser:
 * lo sfondo dell'header (`--fa-color-background`). Stessi valori di index.html e del manifest.
 */
export const THEME_COLOR_BY_SCHEME = { dark: "#0a0f22", light: "#f2f6f8" } as const;

/**
 * I meta theme-color di index.html seguono il tema del telefono (media query); qui li si allinea
 * al tema scelto nell'app, altrimenti con «Scuro» su un telefono chiaro la barra resterebbe chiara.
 */
function applyThemeColorMeta(scheme: "light" | "dark"): void {
  document.querySelectorAll('meta[name="theme-color"]').forEach((meta) => {
    meta.setAttribute("content", THEME_COLOR_BY_SCHEME[scheme]);
  });
}

export function applyDocumentColorScheme(preference = readThemePreference()): "light" | "dark" {
  const scheme = resolveColorScheme(preference, systemColorScheme());
  document.documentElement.dataset.colorScheme = scheme;
  document.documentElement.style.colorScheme = scheme;
  applyThemeColorMeta(scheme);
  return scheme;
}

export function writeThemePreference(preference: ThemePreference): void {
  if (typeof localStorage !== "undefined") {
    localStorage.setItem(STORAGE_KEY, preference);
  }
  applyDocumentColorScheme(preference);
  listeners.forEach((listener) => listener());
}

export function subscribeThemePreference(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}
