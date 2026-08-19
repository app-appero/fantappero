const HEX_PATTERN = /^#([0-9a-fA-F]{6})$/;

function parseHex(hex: string): [number, number, number] {
  const match = HEX_PATTERN.exec(hex);
  if (!match) {
    throw new Error(`Expected #RRGGBB hex color, got "${hex}"`);
  }
  const value = match[1]!;
  return [
    Number.parseInt(value.slice(0, 2), 16),
    Number.parseInt(value.slice(2, 4), 16),
    Number.parseInt(value.slice(4, 6), 16),
  ];
}

function channelToLinear(channel: number): number {
  const normalized = channel / 255;
  return normalized <= 0.03928
    ? normalized / 12.92
    : ((normalized + 0.055) / 1.055) ** 2.4;
}

/** WCAG 2.x relative luminance for sRGB hex colors. */
export function relativeLuminance(hex: string): number {
  const [r, g, b] = parseHex(hex);
  const rl = channelToLinear(r);
  const gl = channelToLinear(g);
  const bl = channelToLinear(b);
  return 0.2126 * rl + 0.7152 * gl + 0.0722 * bl;
}

/** Contrast ratio between two sRGB colors (1–21). */
export function contrastRatio(foreground: string, background: string): number {
  const l1 = relativeLuminance(foreground);
  const l2 = relativeLuminance(background);
  const lighter = Math.max(l1, l2);
  const darker = Math.min(l1, l2);
  return (lighter + 0.05) / (darker + 0.05);
}

export type WcagLevel = "AA" | "AAA";

export type ContrastOptions = {
  /** Large text / UI components threshold (3:1). */
  largeText?: boolean;
  level?: WcagLevel;
};

const THRESHOLDS = {
  AA: { normal: 4.5, large: 3 },
  AAA: { normal: 7, large: 4.5 },
} as const;

/** Returns true if the pair meets WCAG contrast requirements. */
export function meetsWcagContrast(
  foreground: string,
  background: string,
  options: ContrastOptions = {},
): boolean {
  const level = options.level ?? "AA";
  const ratio = contrastRatio(foreground, background);
  const threshold = options.largeText
    ? THRESHOLDS[level].large
    : THRESHOLDS[level].normal;
  return ratio >= threshold;
}
