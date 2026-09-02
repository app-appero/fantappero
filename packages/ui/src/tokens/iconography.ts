/**
 * Iconography guidelines — Lucide (MIT) is the approved icon set.
 * Install in apps when building interactive UI; tokens live here for sizing.
 */

export const iconography = {
  library: "lucide-react",
  license: "MIT",
  strokeWidth: 1.75,
  size: {
    sm: 16,
    md: 20,
    lg: 24,
    xl: 32,
  },
} as const;

export type IconSizeToken = keyof typeof iconography.size;
