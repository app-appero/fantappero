import { DarkTheme, DefaultTheme, type Theme } from "@react-navigation/native";
import { getActiveColorScheme, theme } from "@fantappero/ui/theme";

const { colors } = theme;

/** React Navigation theme aligned with the active color scheme. */
export function buildNavigationTheme(): Theme {
  const base = getActiveColorScheme() === "light" ? DefaultTheme : DarkTheme;
  return {
    ...base,
    colors: {
      ...base.colors,
      primary: colors.accent,
      background: colors.background,
      card: colors.background,
      text: colors.foreground,
      border: colors.border,
      notification: colors.accent,
    },
  };
}

export function buildSceneBackgroundStyle() {
  return {
    backgroundColor: colors.background,
  };
}
