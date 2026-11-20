/**
 * Iniziali per gli avatar senza immagine, uguali su web, app e componenti condivisi.
 *
 * Un nome che inizia con un'emoji dava iniziali rotte («�Ü», QA 19-20/11): `part[0]` e
 * `charAt(0)` prendono una sola unità UTF-16, cioè metà di una coppia surrogata. Qui si conta
 * per grafemi (il carattere che si vede): con `Intl.Segmenter` dove esiste, altrimenti (es.
 * Hermes senza `Intl.Segmenter`) per code point, tenendo attaccati accenti combinanti, selettori
 * di variante, carnagioni, bandiere e sequenze con ZWJ (👩‍💻).
 *
 * Nessun import: i test `node:test` dell'app caricano direttamente questo file.
 */

type GraphemeSegmenter = { segment(input: string): Iterable<{ segment: string }> };
type GraphemeSegmenterConstructor = new (
  locales?: string,
  options?: { granularity: "grapheme" },
) => GraphemeSegmenter;

function graphemeSegmenter(): GraphemeSegmenter | null {
  const Segmenter =
    typeof Intl === "undefined"
      ? undefined
      : (Intl as unknown as { Segmenter?: GraphemeSegmenterConstructor }).Segmenter;
  if (typeof Segmenter !== "function") {
    return null;
  }
  try {
    return new Segmenter(undefined, { granularity: "grapheme" });
  } catch {
    return null;
  }
}

const ZERO_WIDTH_JOINER = 0x200d;

/** Code point che si attaccano al carattere precedente senza formarne uno nuovo. */
function extendsPrevious(codePoint: number): boolean {
  return (
    (codePoint >= 0x0300 && codePoint <= 0x036f) || // accenti combinanti
    (codePoint >= 0x1ab0 && codePoint <= 0x1aff) ||
    (codePoint >= 0x1dc0 && codePoint <= 0x1dff) ||
    (codePoint >= 0x20d0 && codePoint <= 0x20ff) || // segni combinanti per simboli (keycap 1️⃣)
    (codePoint >= 0xfe00 && codePoint <= 0xfe0f) || // selettori di variante (❤️)
    (codePoint >= 0xfe20 && codePoint <= 0xfe2f) ||
    (codePoint >= 0x1f3fb && codePoint <= 0x1f3ff) || // carnagioni (👍🏽)
    (codePoint >= 0xe0020 && codePoint <= 0xe007f) // tag delle bandiere regionali
  );
}

function isRegionalIndicator(codePoint: number): boolean {
  return codePoint >= 0x1f1e6 && codePoint <= 0x1f1ff;
}

/** Ripiego senza `Intl.Segmenter`: grafemi approssimati per code point. */
function codePointGraphemes(text: string, limit: number): string[] {
  const points = Array.from(text);
  const codeOf = (index: number) => points[index]?.codePointAt(0) ?? -1;
  const result: string[] = [];
  let index = 0;
  while (index < points.length && result.length < limit) {
    let cluster = points[index]!;
    index += 1;
    if (isRegionalIndicator(cluster.codePointAt(0) ?? -1) && isRegionalIndicator(codeOf(index))) {
      cluster += points[index]!;
      index += 1;
    }
    while (index < points.length) {
      const next = codeOf(index);
      if (extendsPrevious(next)) {
        cluster += points[index]!;
        index += 1;
      } else if (next === ZERO_WIDTH_JOINER) {
        cluster += points.slice(index, index + 2).join("");
        index += 2;
      } else {
        break;
      }
    }
    result.push(cluster);
  }
  return result;
}

/** I primi `count` caratteri visibili di `text` (un'emoji conta uno, anche se composta). */
export function leadingGraphemes(text: string | null | undefined, count: number): string {
  const value = text ?? "";
  if (!value || count <= 0) {
    return "";
  }
  const segmenter = graphemeSegmenter();
  if (!segmenter) {
    return codePointGraphemes(value, count).join("");
  }
  let result = "";
  let taken = 0;
  for (const { segment } of segmenter.segment(value)) {
    if (taken >= count) {
      break;
    }
    result += segment;
    taken += 1;
  }
  return result;
}

/** Il primo carattere visibile di `text`, o stringa vuota. */
export function firstGrapheme(text: string | null | undefined): string {
  return leadingGraphemes(text, 1);
}

/** Iniziale singola (in maiuscolo) per un avatar; `fallback` se il nome è vuoto. */
export function avatarInitial(name: string | null | undefined, fallback = "?"): string {
  return firstGrapheme((name ?? "").trim()).toUpperCase() || fallback;
}

/** Le prime `count` lettere del nome, spazi esclusi e in maiuscolo: «Lega Amici» → «LE». */
export function avatarLetters(name: string | null | undefined, count = 2, fallback = "?"): string {
  return leadingGraphemes((name ?? "").replace(/\s+/g, ""), count).toUpperCase() || fallback;
}

export type AvatarInitialsOptions = {
  /** Da quali parole prendere le iniziali: le prime due (default) o la prima e l'ultima. */
  words?: "first-two" | "first-last";
  /** Con una parola sola, quanti caratteri mostrare (default 1). */
  singleWordLength?: 1 | 2;
  /** Nome vuoto o di soli spazi (default «?»). */
  fallback?: string;
};

/** Due iniziali (in maiuscolo) per un avatar: «Mario Rossi» → «MR», «😀 Ümit» → «😀Ü». */
export function avatarInitials(
  name: string | null | undefined,
  options: AvatarInitialsOptions = {},
): string {
  const parts = (name ?? "").trim().split(/\s+/).filter(Boolean);
  const [first] = parts;
  if (!first) {
    return options.fallback ?? "?";
  }
  if (parts.length === 1) {
    return leadingGraphemes(first, options.singleWordLength ?? 1).toUpperCase();
  }
  const second = options.words === "first-last" ? parts[parts.length - 1] : parts[1];
  return `${firstGrapheme(first)}${firstGrapheme(second)}`.toUpperCase();
}
