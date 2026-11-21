// Ricerca senza accenti e senza maiuscole: "dembele" trova "A. Dembélé" (QA 18/11).

// Lettere che la scomposizione Unicode (NFD) non separa dall'accento.
const NON_DECOMPOSING: Record<string, string> = {
  ø: "o",
  ł: "l",
  đ: "d",
  ð: "d",
  ß: "ss",
  æ: "ae",
  œ: "oe",
  ı: "i",
  þ: "th",
};

const COMBINING_MARKS = /[̀-ͯ]/g;
const NON_DECOMPOSING_PATTERN = /[øłđðßæœıþ]/g;

// Testo UTF-8 letto per sbaglio come Latin-1 o Windows-1252 (mojibake): "ć" diventa "Ä\u0087"
// o "Ä‡", "é" diventa "Ã©". Quattro nomi del listone erano arrivati così e "jovanovic" non
// trovava "L. JovanoviÄ\u0087" (QA 20-21/11). Stessa riparazione prudente del backend
// (`repair_mojibake`): solo sequenze UTF-8 valide byte per byte, il resto resta com'è.
// Uguale nell'app (`listoneFilter.ts`).
const CP1252_BYTES: Record<string, number> = {
  "€": 0x80, "‚": 0x82, "ƒ": 0x83, "„": 0x84, "…": 0x85, "†": 0x86, "‡": 0x87, "ˆ": 0x88,
  "‰": 0x89, "Š": 0x8a, "‹": 0x8b, "Œ": 0x8c, "Ž": 0x8e, "‘": 0x91, "’": 0x92, "“": 0x93,
  "”": 0x94, "•": 0x95, "–": 0x96, "—": 0x97, "˜": 0x98, "™": 0x99, "š": 0x9a, "›": 0x9b,
  "œ": 0x9c, "ž": 0x9e, "Ÿ": 0x9f,
};
const CONTINUATION = `[\\u0080-\\u00bf${Object.keys(CP1252_BYTES).join("")}]`;
const MOJIBAKE_SEQUENCE = new RegExp(
  `[\\u00c2-\\u00df]${CONTINUATION}|[\\u00e0-\\u00ef]${CONTINUATION}{2}|[\\u00f0-\\u00f4]${CONTINUATION}{3}`,
  "g",
);
const MAX_REPAIR_PASSES = 3;

function mojibakeByte(char: string): number {
  const code = char.charCodeAt(0);
  return code <= 0xff ? code : (CP1252_BYTES[char] ?? -1);
}

function repairSequence(sequence: string): string {
  const bytes = Array.from(sequence, mojibakeByte);
  if (bytes.some((byte) => byte < 0)) {
    return sequence;
  }
  const lead = bytes[0] ?? 0;
  const leadBits = bytes.length === 2 ? lead & 0x1f : bytes.length === 3 ? lead & 0x0f : lead & 0x07;
  const codePoint = bytes.slice(1).reduce((acc, byte) => (acc << 6) | (byte & 0x3f), leadBits);
  const minimum = bytes.length === 2 ? 0x80 : bytes.length === 3 ? 0x800 : 0x10000;
  // Niente forme troppo lunghe, surrogati, controlli o oltre l'ultimo punto Unicode.
  if (
    codePoint < minimum ||
    codePoint < 0xa0 ||
    (codePoint >= 0xd800 && codePoint <= 0xdfff) ||
    codePoint > 0x10ffff
  ) {
    return sequence;
  }
  return String.fromCodePoint(codePoint);
}

/** Ripara il testo UTF-8 letto come Latin-1/Windows-1252; un testo giusto non cambia. */
export function repairMojibake(value: string): string {
  let repaired = value;
  for (let pass = 0; pass < MAX_REPAIR_PASSES; pass += 1) {
    const candidate = repaired.replace(MOJIBAKE_SEQUENCE, repairSequence);
    if (candidate === repaired) {
      break;
    }
    repaired = candidate;
  }
  return repaired;
}

export function foldSearchText(value: string): string {
  // Prima la codifica: dopo le minuscole "Ä" diventa "ä" e la sequenza non si riconosce più.
  const lowered = repairMojibake(value).toLocaleLowerCase("it-IT");
  const decomposed = typeof lowered.normalize === "function" ? lowered.normalize("NFD") : lowered;
  return decomposed
    .replace(COMBINING_MARKS, "")
    .replace(NON_DECOMPOSING_PATTERN, (char) => NON_DECOMPOSING[char] ?? char)
    .trim();
}

/** `true` se `haystack` contiene `query`, ignorando accenti e maiuscole. */
export function matchesSearch(haystack: string, query: string): boolean {
  const needle = foldSearchText(query);
  return needle.length === 0 || foldSearchText(haystack).includes(needle);
}
