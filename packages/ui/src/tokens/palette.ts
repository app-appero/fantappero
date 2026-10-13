/** Raw palette — single source for hex values (no hardcoding in apps). */

export const palette = {
  /** Blu notte: sfondi e superfici del tema scuro. */
  pitch950: "#060913",
  pitch900: "#080c1c",
  pitch800: "#0a0f22",
  pitch700: "#141a36",
  pitch600: "#262e52",
  pitch500: "#3c4775",

  ivory50: "#f7f9ff",
  ivory100: "#f4f6ff",
  ivory200: "#e2e8f5",

  /** Grigi-blu per testo secondario. */
  slate300: "#a5b0d6",
  slate400: "#8c97c0",
  slate500: "#58648a",

  /** Azzurro: colore di marca primario. */
  electric600: "#2f63f0",
  electric500: "#5aa2ff",
  electric400: "#8dbbff",
  electric300: "#bbd6ff",

  /** Cobalto: azzurro di marca sul tema chiaro (contrasto con testo bianco). */
  cobalt700: "#1749b8",
  cobalt600: "#1f5ee6",

  /** Marca: blu → viola. Pulsanti principali e logo (testo bianco sopra). */
  brand600: "#3560f0",
  brand500: "#4f5cf5",
  violet500: "#7a4dff",
  violet600: "#6a3fe0",
  violet400: "#9b6bff",
  onBrand: "#ffffff",

  /** Menta: solo per lo stato "successo" (non è un colore di marca). */
  mint600: "#0b8a6b",
  mint500: "#3ddc97",
  mint400: "#7be8b8",

  /** Testo scuro da usare sopra il gradiente azzurro-menta. */
  navy900: "#06121f",

  /** Campo da gioco. */
  field800: "#14213f",
  field700: "#101a36",
  fieldLight800: "#1f4fb8",
  fieldLight700: "#1a45a5",

  /** Sfondi del tema chiaro (bianco freddo). */
  cloud50: "#f2f6f8",
  cloud100: "#e8eef2",
  cloud200: "#dce5eb",

  success600: "#0b8a6b",
  success500: "#3ddc97",
  success400: "#7be8b8",

  warning600: "#b8860b",
  warning500: "#e6a700",
  warning400: "#f0c040",

  danger600: "#c92a2a",
  danger500: "#e03131",
  danger400: "#f06565",

  focusRing: "#bbd6ff",
} as const;

export type PaletteToken = keyof typeof palette;
