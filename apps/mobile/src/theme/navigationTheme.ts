import { DarkTheme, type Theme } from "@react-navigation/native";
import { theme } from "@fantappero/ui/theme";

const { colors } = theme;

/** React Navigation theme aligned with EPUI-01 tokens (dark pitch surface). */
export const appNavigationTheme: Theme = {
  ...DarkTheme,
  colors: {
    ...DarkTheme.colors,
    primary: colors.accent,
    background: colors.background,
    card: colors.background,
    text: colors.foreground,
    border: colors.border,
    notification: colors.accent,
  },
};

export const sceneBackgroundStyle = {
  backgroundColor: colors.background,
} as const;
