import {
  applyColorScheme,
  darkColors,
  lightColors,
  resolveColorScheme,
  type AppColors,
  type ThemePreference,
} from "@fantappero/ui/theme";
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { Appearance, useColorScheme } from "react-native";
import { loadThemePreference, saveThemePreference } from "./themePreferenceStorage";

type AppThemeContextValue = {
  preference: ThemePreference;
  setPreference: (preference: ThemePreference) => void;
  scheme: "light" | "dark";
  /**
   * Stessi valori dell'oggetto `colors` condiviso (mutato a ogni cambio tema),
   * ma calcolati qui con `useMemo` legato a `scheme`: un componente che li
   * legge da qui invece che dall'oggetto condiviso ha la garanzia di React
   * di vedere sempre la coppia (scheme, colori) coerente nello stesso render,
   * senza dipendere dal momento esatto in cui rilegge una proprietà mutata
   * altrove. Usarli per un componente che si è visto restare "indietro" col
   * tema nonostante si colleghi già al contesto.
   */
  resolvedColors: AppColors;
};

const AppThemeContext = createContext<AppThemeContextValue | null>(null);

export function AppThemeProvider({ children }: { children: ReactNode }) {
  const systemScheme = useColorScheme();
  const [preference, setPreferenceState] = useState<ThemePreference>("system");

  useEffect(() => {
    let cancelled = false;
    void loadThemePreference().then((stored) => {
      if (!cancelled) {
        setPreferenceState(stored);
      }
    });
    return () => {
      cancelled = true;
    };
  }, []);

  const scheme = resolveColorScheme(preference, systemScheme);
  applyColorScheme(scheme);
  const resolvedColors = useMemo(
    () => (scheme === "light" ? lightColors : darkColors),
    [scheme],
  );

  useEffect(() => {
    Appearance.setColorScheme(preference === "system" ? "unspecified" : preference);
  }, [preference]);

  const setPreference = useCallback((next: ThemePreference) => {
    setPreferenceState(next);
    void saveThemePreference(next);
  }, []);

  const value = useMemo(
    () => ({ preference, setPreference, scheme, resolvedColors }),
    [preference, setPreference, scheme, resolvedColors],
  );

  return <AppThemeContext.Provider value={value}>{children}</AppThemeContext.Provider>;
}

export function useAppTheme(): AppThemeContextValue {
  const value = useContext(AppThemeContext);
  if (!value) {
    throw new Error("useAppTheme must be used within AppThemeProvider");
  }
  return value;
}
