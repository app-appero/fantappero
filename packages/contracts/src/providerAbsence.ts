/**
 * Assenze dei giocatori nelle partite dei turni europei, in italiano (1.5, Rosario 27/11).
 *
 * Lo stato e il rientro arrivano dal fornitore delle probabili formazioni in inglese
 * («Doubtful», «Mid December 2026», «Early January 2027»…) e finivano così sullo schermo
 * «Partita» e negli elenchi della Formazione. Qui sta l'UNICA funzione che li traduce, per
 * sito e app: il server continua a mandare il testo originale (l'app 1.4 già installata lo
 * legge com'è) e ogni schermata lo passa da qui prima di mostrarlo.
 *
 * Solo logica pura. Un testo che non si riconosce resta com'è: meglio l'originale di un
 * testo inventato.
 */

const MONTHS: Record<string, string> = {
  january: "gennaio",
  jan: "gennaio",
  february: "febbraio",
  feb: "febbraio",
  march: "marzo",
  mar: "marzo",
  april: "aprile",
  apr: "aprile",
  may: "maggio",
  june: "giugno",
  jun: "giugno",
  july: "luglio",
  jul: "luglio",
  august: "agosto",
  aug: "agosto",
  september: "settembre",
  sept: "settembre",
  sep: "settembre",
  october: "ottobre",
  oct: "ottobre",
  november: "novembre",
  nov: "novembre",
  december: "dicembre",
  dec: "dicembre",
};

const MONTH_NAMES = Object.keys(MONTHS)
  .sort((a, b) => b.length - a.length)
  .join("|");

/** «early / mid / late» davanti al mese: «inizio», «metà», «fine». */
const PERIOD_WORDS: Record<string, string> = {
  early: "inizio",
  beginning: "inizio",
  "beginning of": "inizio",
  "start of": "inizio",
  mid: "metà",
  middle: "metà",
  "middle of": "metà",
  late: "fine",
  end: "fine",
  "end of": "fine",
};

const PERIOD_ALTERNATION =
  "early|beginning of|beginning|start of|mid|middle of|middle|late|end of|end";

/** Stati e frasi intere (confronto in minuscolo, trattini e spazi doppi ridotti a uno spazio). */
const PHRASES: Record<string, string> = {
  doubtful: "Dubbio",
  questionable: "Dubbio",
  uncertain: "Dubbio",
  doubt: "Dubbio",
  "in doubt": "Dubbio",
  "50 50": "Dubbio",
  out: "Fuori",
  "ruled out": "Fuori",
  "missing fixture": "Assente",
  absent: "Assente",
  suspended: "Squalificato",
  suspension: "Squalificato",
  banned: "Squalificato",
  injured: "Infortunato",
  injury: "Infortunato",
  "red card": "Espulso",
  red: "Espulso",
  "sent off": "Espulso",
  "day to day": "Giorno per giorno",
  "week to week": "Settimana per settimana",
  unavailable: "Indisponibile",
  available: "Disponibile",
  fit: "Disponibile",
  illness: "Malattia",
  ill: "Malattia",
  sick: "Malattia",
  "personal reasons": "Motivi personali",
  "international duty": "Impegno con la nazionale",
  rest: "Riposo",
  rested: "Riposo",
  unknown: "rientro non noto",
  "back in training": "di nuovo in allenamento",
  "back in team training": "di nuovo in allenamento",
  "a few days": "qualche giorno",
  "few days": "qualche giorno",
  "a few weeks": "qualche settimana",
  "few weeks": "qualche settimana",
  "a few months": "qualche mese",
  "few months": "qualche mese",
  "several weeks": "diverse settimane",
  "several months": "diversi mesi",
  "next week": "prossima settimana",
  "this week": "questa settimana",
  "next match": "prossima partita",
  "next game": "prossima partita",
  "end of season": "fine stagione",
  "end of the season": "fine stagione",
  "next season": "prossima stagione",
  "after the international break": "dopo la sosta",
  "after international break": "dopo la sosta",
};

function normalize(text: string): string {
  return text
    .trim()
    .toLowerCase()
    .replace(/[_-]+/g, " ")
    .replace(/\s+/g, " ")
    .replace(/[.!]+$/, "");
}

function pad2(value: number): string {
  return value < 10 ? `0${value}` : String(value);
}

function translateDate(raw: string): string | null {
  // «2026-12-12» (anche con l'ora): data già in numeri, resta precisa: «12/12/2026».
  const iso = /^(\d{4})-(\d{2})-(\d{2})(?:[t ].*)?$/i.exec(raw.trim());
  if (iso) {
    const year = Number(iso[1]);
    const month = Number(iso[2]);
    const day = Number(iso[3]);
    if (month >= 1 && month <= 12 && day >= 1 && day <= 31) {
      return `${pad2(day)}/${pad2(month)}/${year}`;
    }
    return null;
  }
  const text = raw.trim().toLowerCase().replace(/\s+/g, " ").replace(/[.!]+$/, "");
  // «12 Dec 2026», «12th December 2026», «12 December».
  const dayFirst = new RegExp(`^(\\d{1,2})(?:st|nd|rd|th)?\\s+(${MONTH_NAMES})\\.?(?:,?\\s+(\\d{4}))?$`).exec(text);
  if (dayFirst) {
    const month = MONTHS[dayFirst[2] ?? ""];
    const year = dayFirst[3];
    return month ? `${Number(dayFirst[1])} ${month}${year ? ` ${year}` : ""}` : null;
  }
  // «Dec 12, 2026», «December 12th 2026».
  const monthFirst = new RegExp(`^(${MONTH_NAMES})\\.?\\s+(\\d{1,2})(?:st|nd|rd|th)?(?:,?\\s+(\\d{4}))?$`).exec(text);
  if (monthFirst) {
    const month = MONTHS[monthFirst[1] ?? ""];
    const year = monthFirst[3];
    return month ? `${Number(monthFirst[2])} ${month}${year ? ` ${year}` : ""}` : null;
  }
  return null;
}

function translatePeriod(text: string): string | null {
  // «Mid December 2026», «Early January», «Late February 2027», «December 2026», «End of May».
  const monthMatch = new RegExp(
    `^(?:(${PERIOD_ALTERNATION})\\s+)?(?:the\\s+)?(${MONTH_NAMES})\\.?(?:\\s+(\\d{4}))?$`,
  ).exec(text);
  if (monthMatch) {
    const month = MONTHS[monthMatch[2] ?? ""];
    if (!month) {
      return null;
    }
    const period = monthMatch[1] ? PERIOD_WORDS[monthMatch[1]] : null;
    const year = monthMatch[3];
    return [period, month, year].filter(Boolean).join(" ");
  }
  // «Early 2027», «Late 2026».
  const yearMatch = new RegExp(`^(${PERIOD_ALTERNATION})\\s+(\\d{4})$`).exec(text);
  if (yearMatch) {
    const period = PERIOD_WORDS[yearMatch[1] ?? ""];
    return period ? `${period} ${yearMatch[2]}` : null;
  }
  return null;
}

const DURATION_UNIT: Record<string, [string, string]> = {
  day: ["giorno", "giorni"],
  week: ["settimana", "settimane"],
  month: ["mese", "mesi"],
};

function translateDuration(text: string): string | null {
  // «3 weeks», «2-3 weeks» (il trattino è già uno spazio), «2 to 3 weeks», «around 4 months».
  const match =
    /^(?:(around|about|approximately|approx|circa|~)\s*)?(\d{1,3})(?:\s+(?:to\s+)?(\d{1,3}))?\s*(day|week|month)s?$/.exec(
      text,
    );
  if (!match) {
    return null;
  }
  const unit = DURATION_UNIT[match[4] ?? ""];
  if (!unit) {
    return null;
  }
  const first = Number(match[2]);
  const second = match[3] === undefined ? null : Number(match[3]);
  const amount = second === null ? String(first) : `${first}-${second}`;
  const plural = second !== null || first !== 1;
  return `${match[1] ? "circa " : ""}${amount} ${plural ? unit[1] : unit[0]}`;
}

function translateWhole(raw: string): string | null {
  const date = translateDate(raw);
  if (date !== null) {
    return date;
  }
  const text = normalize(raw);
  const phrase = PHRASES[text];
  if (phrase !== undefined) {
    return phrase;
  }
  return translatePeriod(text) ?? translateDuration(text);
}

/**
 * Testo del fornitore su stato o rientro di un'assenza, in italiano.
 * «Doubtful» → «Dubbio»; «Mid December 2026» → «metà dicembre 2026»;
 * «Early December 2026» → «inizio dicembre 2026»; «Late February 2027» → «fine febbraio 2027»;
 * «2026-12-12» → «12/12/2026». Vuoto → `null`; un testo non riconosciuto torna com'è
 * (già in italiano, per esempio). Più parti separate da virgola o trattino si traducono una
 * per una.
 */
export function italianAbsenceText(text: string | null | undefined): string | null {
  if (typeof text !== "string") {
    return null;
  }
  const trimmed = text.trim();
  if (trimmed === "") {
    return null;
  }
  const whole = translateWhole(trimmed);
  if (whole !== null) {
    return whole;
  }
  const parts = trimmed.split(/\s*[,;|·]\s*|\s+[-–]\s+/).filter((part) => part !== "");
  if (parts.length > 1) {
    const translated = parts.map((part) => translateWhole(part));
    if (translated.some((part) => part !== null)) {
      return parts.map((part, index) => translated[index] ?? part).join(", ");
    }
  }
  return trimmed;
}

const KIND_LABEL: Record<string, string> = {
  injury: "Infortunio",
  injured: "Infortunio",
  suspension: "Squalifica",
  suspended: "Squalifica",
  red: "Espulsione",
  red_card: "Espulsione",
  redcard: "Espulsione",
  "red card": "Espulsione",
  doubtful: "Dubbio",
  questionable: "Dubbio",
  uncertain: "Dubbio",
  out: "Fuori",
  "missing fixture": "Assente",
  illness: "Malattia",
  "personal reasons": "Motivi personali",
  "international duty": "Impegno con la nazionale",
};

/** Tipo di assenza: «Infortunio», «Squalifica», «Espulsione»… Senza tipo noto: «Indisponibile». */
export function absenceKindLabel(kind: string | null | undefined): string {
  const normalized = (kind ?? "").trim().toLowerCase();
  return KIND_LABEL[normalized] ?? KIND_LABEL[normalized.replace(/[_-]+/g, " ")] ?? "Indisponibile";
}

/**
 * Riga «Infortunio · metà dicembre 2026» dell'elenco «Infortunati e squalificati»: il tipo
 * dell'assenza e, dopo il punto, stato o rientro tradotti. Se i due dicono la stessa cosa
 * («Dubbio» e «Doubtful») si scrive una volta sola.
 */
export function absenceLine(
  kind: string | null | undefined,
  label: string | null | undefined,
): string {
  const kindLabel = absenceKindLabel(kind);
  const text = italianAbsenceText(label);
  if (text === null || text.toLowerCase() === kindLabel.toLowerCase()) {
    return kindLabel;
  }
  return `${kindLabel} · ${text}`;
}

/**
 * Nota di un «in dubbio» nella lista «Cambia» e nelle note: sempre «Dubbio», più lo stato o il
 * rientro del fornitore tradotti quando dicono qualcosa in più («Dubbio · giorno per giorno»).
 */
export function doubtNoteText(note: string | null | undefined): string {
  const text = italianAbsenceText(note);
  if (text === null || text.toLowerCase() === "dubbio") {
    return "Dubbio";
  }
  return `Dubbio · ${text.charAt(0).toLowerCase()}${text.slice(1)}`;
}
