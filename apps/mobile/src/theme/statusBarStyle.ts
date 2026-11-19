/** Icone della status bar come in `expo-status-bar`: `light` = icone chiare, `dark` = icone scure. */
export type StatusBarIconStyle = "light" | "dark";

const HEX_COLOR = /^#([0-9a-f]{3}|[0-9a-f]{6})$/i;

/** Luminanza relativa WCAG di un colore `#rgb` / `#rrggbb`; `null` per altri formati. */
function relativeLuminance(color: string): number | null {
  const match = HEX_COLOR.exec(color.trim());
  if (!match) {
    return null;
  }
  const digits = match[1]!;
  const full = digits.length === 3 ? [...digits].map((digit) => digit + digit).join("") : digits;
  const [r, g, b] = [0, 2, 4].map((start) => {
    const channel = Number.parseInt(full.slice(start, start + 2), 16) / 255;
    return channel <= 0.03928 ? channel / 12.92 : ((channel + 0.055) / 1.055) ** 2.4;
  }) as [number, number, number];
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

/**
 * Sceglie icone chiare o scure guardando il colore che sta davvero dietro la status bar
 * (lo sfondo dell'app), non solo il nome del tema: vince il bianco o il nero, quello che
 * ha più contrasto. Con un colore non esadecimale (es. `rgba(...)`) vale `fallback`.
 */
export function statusBarStyleForBackground(
  background: string,
  fallback: StatusBarIconStyle,
): StatusBarIconStyle {
  const luminance = relativeLuminance(background);
  if (luminance === null) {
    return fallback;
  }
  const contrastWithWhite = 1.05 / (luminance + 0.05);
  const contrastWithBlack = (luminance + 0.05) / 0.05;
  return contrastWithWhite >= contrastWithBlack ? "light" : "dark";
}
