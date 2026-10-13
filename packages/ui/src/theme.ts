import { applyColorScheme, colors, getActiveColorScheme } from "./tokens/colors.js";
import {
  resolveColorScheme,
  type ResolvedColorScheme,
  type ThemePreference,
} from "./tokens/colorSchemes.js";
import { spacing, density } from "./tokens/spacing.js";
import { textRoles, typography as typeScale } from "./tokens/typography.js";
import { radius } from "./tokens/radius.js";
import { shadows } from "./tokens/shadows.js";
import { motion } from "./tokens/motion.js";
import { breakpoints } from "./tokens/breakpoints.js";
import { zIndex } from "./tokens/zIndex.js";
import { iconography } from "./tokens/iconography.js";
import { illustration } from "./tokens/illustration.js";
import { visualPrinciples } from "./tokens/principles.js";

export {
  applyColorScheme,
  getActiveColorScheme,
  resolveColorScheme,
  type ResolvedColorScheme,
  type ThemePreference,
};

/** Colori della cornice olografica ("figurina"), in ordine di giro. */
export const foil = ["#ff7ad9", "#ffd66e", "#7cf7c8", "#6ec8ff", "#b28cff", "#ff7ad9"] as const;

/** Combined theme object for React Native and programmatic consumers. */
export const theme = {
  colors,
  spacing,
  density,
  typography: typeScale,
  textRoles,
  radius,
  shadows,
  motion,
  breakpoints,
  zIndex,
  iconography,
  illustration,
  visualPrinciples,
  foil,
} as const;
