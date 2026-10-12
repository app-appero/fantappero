/** Raw palette — single source for hex values (no hardcoding in apps). */

export const palette = {
  /** Blu notte: sfondi e superfici del tema scuro. */
  pitch950: "#0c1730",
  pitch900: "#101c38",
  pitch800: "#13213f",
  pitch700: "#1c2d54",
  pitch600: "#2b3f6e",
  pitch500: "#4a6199",

  ivory50: "#f7f9ff",
  ivory100: "#f5f6fa",
  ivory200: "#e4e9f5",

  /** Grigi-blu per testo secondario. */
  slate300: "#b4bfdd",
  slate400: "#98a5c9",
  slate500: "#5d6a8f",

  /** Azzurro cielo: colore di marca sul tema scuro. */
  electric600: "#4c86ff",
  electric500: "#6aa8ff",
  electric400: "#8cc4ff",
  electric300: "#b5d6ff",

  /** Cobalto: colore di marca sul tema chiaro (contrasto con testo bianco). */
  cobalt700: "#1f43b8",
  cobalt600: "#2b57e0",

  /** Testo scuro da usare sopra l'azzurro cielo. */
  navy900: "#0a1530",

  /** Sfondi del tema chiaro (bianco freddo). */
  cloud50: "#f4f7fd",
  cloud100: "#e9eefa",
  cloud200: "#dde6f8",

  success600: "#17707c",
  success500: "#38c9d8",
  success400: "#6fe0ea",

  warning600: "#b8860b",
  warning500: "#e6a700",
  warning400: "#f0c040",

  danger600: "#c92a2a",
  danger500: "#e03131",
  danger400: "#f06565",

  focusRing: "#b5d6ff",
} as const;

export type PaletteToken = keyof typeof palette;
