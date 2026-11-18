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

export function foldSearchText(value: string): string {
  const lowered = value.toLocaleLowerCase("it-IT");
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
