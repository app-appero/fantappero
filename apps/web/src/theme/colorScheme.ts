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

export function applyDocumentColorScheme(preference = readThemePreference()): "light" | "dark" {
  const scheme = resolveColorScheme(preference, systemColorScheme());
  document.documentElement.dataset.colorScheme = scheme;
  document.documentElement.style.colorScheme = scheme;
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
