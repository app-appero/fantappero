/** Raw palette — single source for hex values (no hardcoding in apps). */

export const palette = {
  pitch950: "#060910",
  pitch900: "#0a0e14",
  pitch800: "#0f1419",
  pitch700: "#1c2736",
  pitch600: "#2a3544",
  pitch500: "#3d4a5c",

  ivory50: "#faf8f4",
  ivory100: "#f4f1ea",
  ivory200: "#e8e4db",

  slate300: "#a3abbe",
  slate400: "#8b93a7",
  slate500: "#6b7389",

  electric600: "#1f57c9",
  electric500: "#2f6fed",
  electric400: "#5a8df2",
  electric300: "#8fb0f7",

  success600: "#247a35",
  success500: "#2f9e44",
  success400: "#4cb564",

  warning600: "#b8860b",
  warning500: "#e6a700",
  warning400: "#f0c040",

  danger600: "#c92a2a",
  danger500: "#e03131",
  danger400: "#f06565",

  focusRing: "#8fb0f7",
} as const;

export type PaletteToken = keyof typeof palette;
