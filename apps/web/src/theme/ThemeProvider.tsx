import { createContext, useContext, useEffect, useMemo, type ReactNode } from "react";
import { useLocation } from "../router/simpleRouter";

/** Supported visual themes — extensible for future i18n / light mode. */
export type AppThemeId = "fantappero";

export type AppSurface = "app" | "admin" | "auth";

export type ThemeContextValue = {
  themeId: AppThemeId;
  surface: AppSurface;
};

const ThemeContext = createContext<ThemeContextValue | null>(null);

/** Applies design tokens to the document root (testable without React effects). */
export function applyDocumentTheme(themeId: AppThemeId, surface: AppSurface): void {
  document.documentElement.lang = "it";
  document.documentElement.dataset.theme = themeId;
  document.body.dataset.surface = surface;
}

export function resolveSurface(pathname: string): AppSurface {
  if (pathname.startsWith("/admin")) {
    return "admin";
  }
  if (pathname.startsWith("/accedi")) {
    return "auth";
  }
  return "app";
}

export type ThemeProviderProps = {
  children: ReactNode;
  themeId?: AppThemeId;
};

/** Applies design tokens to the document and exposes surface for layout styling. */
export function ThemeProvider({ children, themeId = "fantappero" }: ThemeProviderProps) {
  const { pathname } = useLocation();
  const surface = resolveSurface(pathname);

  useEffect(() => {
    applyDocumentTheme(themeId, surface);
  }, [themeId, surface]);

  const value = useMemo<ThemeContextValue>(() => ({ themeId, surface }), [themeId, surface]);

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function useTheme(): ThemeContextValue {
  const context = useContext(ThemeContext);
  if (!context) {
    throw new Error("useTheme must be used within ThemeProvider");
  }
  return context;
}
