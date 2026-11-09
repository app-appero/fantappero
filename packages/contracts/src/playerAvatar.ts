/**
 * Avatar dei calciatori: busto stilizzato senza volto, generato in SVG dal client.
 * Nessuna foto (niente diritti d'immagine): la maglia ha i colori del club reale
 * (senza stemma né sponsor); capelli, carnagione e barba sono assegnati in modo
 * stabile a partire dall'id del calciatore. Lo stesso SVG vale per web e app.
 */
export type KitPattern = "plain" | "stripes" | "halves" | "sash" | "sleeves" | "band" | "hoops";

export interface ClubKit {
  primary: string;
  secondary: string;
  pattern: KitPattern;
  /** Colore del colletto. */
  trim: string;
}

type KitRow = readonly [aliases: string, primary: string, secondary: string, pattern: KitPattern, trim: string];

const K = (
  aliases: string,
  primary: string,
  secondary: string,
  pattern: KitPattern,
  trim: string = secondary,
): KitRow => [aliases, primary, secondary, pattern, trim];

const BLACK = "#0B0F1E";
const WHITE = "#F6F6F6";

/** Alias separati da `|`, già normalizzabili (minuscole, senza accenti e simboli). */
const CLUB_ROWS: readonly KitRow[] = [
  // Serie A
  K("atalanta", BLACK, "#1E73BE", "stripes"),
  K("bologna", "#9E1B32", "#0B2A6B", "stripes", "#0B2A6B"),
  K("cagliari", "#9E1B32", "#0B2A6B", "stripes", "#0B2A6B"),
  K("como", "#2B5FB8", "#FFFFFF", "plain", WHITE),
  K("cremonese", "#B8B8B8", "#9E1B32", "stripes", "#9E1B32"),
  K("fiorentina", "#6B2FB8", "#3A1D80", "plain", WHITE),
  K("genoa", "#9E1B32", "#0B2A6B", "halves", "#0B2A6B"),
  K("hellas verona|verona", "#F2C400", "#0B2A6B", "plain", "#0B2A6B"),
  K("inter|internazionale|inter milan", "#0A3FA0", BLACK, "stripes", BLACK),
  K("juventus|juve", WHITE, BLACK, "stripes", BLACK),
  K("lazio|ss lazio", "#8FD0F5", "#FFFFFF", "plain", WHITE),
  K("lecce|us lecce", "#E4B100", "#C8102E", "stripes", "#C8102E"),
  K("milan|ac milan", "#D01F2E", BLACK, "stripes", BLACK),
  K("napoli|ssc napoli", "#4DA8E8", "#2E86C9", "plain", WHITE),
  K("parma", WHITE, "#F2C400", "band", "#F2C400"),
  K("pisa", "#0B0F1E", "#2B5FB8", "stripes", "#2B5FB8"),
  K("roma|as roma", "#8E1F2F", "#F2B705", "sleeves", "#F2B705"),
  K("sassuolo", "#1E8E4E", BLACK, "stripes", BLACK),
  K("torino", "#7A1B2D", "#F6F6F6", "plain", WHITE),
  K("udinese", WHITE, BLACK, "stripes", BLACK),
  K("empoli", "#2B7FD4", WHITE, "plain", WHITE),
  K("monza|ac monza", "#D01F2E", WHITE, "plain", WHITE),
  K("salernitana", "#7A1B2D", WHITE, "plain", WHITE),
  K("venezia", "#0B0F1E", "#1E8E4E", "halves", "#F2B705"),
  // Premier League
  K("arsenal", "#E02B2B", WHITE, "sleeves"),
  K("aston villa", "#7A1B3C", "#8FD0F5", "sleeves", "#8FD0F5"),
  K("bournemouth|afc bournemouth", "#D01F2E", BLACK, "stripes", BLACK),
  K("brentford", "#E02B2B", WHITE, "stripes", BLACK),
  K("brighton|brighton hove albion", "#2B6FD4", WHITE, "stripes", WHITE),
  K("burnley", "#7A1B3C", "#8FD0F5", "sleeves", "#8FD0F5"),
  K("chelsea", "#1F3FA0", WHITE, "plain", WHITE),
  K("crystal palace", "#1F3FA0", "#D01F2E", "stripes", "#D01F2E"),
  K("everton", "#2B5FB8", WHITE, "plain", WHITE),
  K("fulham", WHITE, BLACK, "plain", BLACK),
  K("leeds|leeds united", WHITE, "#F2C400", "plain", "#F2C400"),
  K("liverpool", "#D1202F", "#9E1520", "plain", "#F5D26B"),
  K("manchester city|man city", "#8FCBF2", WHITE, "plain", WHITE),
  K("manchester united|man united", "#D01F2E", BLACK, "plain", BLACK),
  K("newcastle|newcastle united", WHITE, BLACK, "stripes", BLACK),
  K("nottingham forest|nott forest", "#D01F2E", WHITE, "plain", WHITE),
  K("sunderland", "#D01F2E", WHITE, "stripes", BLACK),
  K("tottenham|tottenham hotspur", WHITE, "#12204D", "plain", "#12204D"),
  K("west ham|west ham united", "#7A1B3C", "#8FD0F5", "sleeves", "#8FD0F5"),
  K("wolves|wolverhampton|wolverhampton wanderers", "#F2A900", BLACK, "plain", BLACK),
  K("sheffield utd|sheffield united", "#D01F2E", WHITE, "stripes", BLACK),
  K("leicester|leicester city", "#2B5FB8", WHITE, "plain", WHITE),
  K("southampton", "#D01F2E", WHITE, "stripes", BLACK),
  K("ipswich|ipswich town", "#2B5FB8", WHITE, "plain", WHITE),
  // LaLiga
  K("alaves|deportivo alaves", "#2B5FB8", WHITE, "stripes", WHITE),
  K("athletic club|athletic bilbao", "#D01F2E", WHITE, "stripes", BLACK),
  K("atletico madrid|atletico de madrid", "#D82B2B", WHITE, "stripes", "#0B2A6B"),
  K("barcelona|fc barcelona", "#A31D4A", "#0B3A8C", "stripes", "#F3C623"),
  K("celta vigo|celta", "#8FD0F5", WHITE, "plain", "#D01F2E"),
  K("elche", WHITE, "#1E8E4E", "band", "#1E8E4E"),
  K("espanyol", "#2B5FB8", WHITE, "stripes", WHITE),
  K("getafe", "#2B5FB8", WHITE, "plain", WHITE),
  K("girona", "#D01F2E", WHITE, "plain", WHITE),
  K("levante", "#9E1B32", "#0B2A6B", "stripes", "#0B2A6B"),
  K("mallorca|rcd mallorca", "#D01F2E", BLACK, "plain", BLACK),
  K("osasuna|ca osasuna", "#C8102E", "#0B2A6B", "plain", "#0B2A6B"),
  K("real oviedo|oviedo", "#2B5FB8", WHITE, "plain", WHITE),
  K("rayo vallecano|rayo", WHITE, "#D01F2E", "sash", "#D01F2E"),
  K("real betis|betis", "#1E8E4E", WHITE, "stripes", WHITE),
  K("real madrid", WHITE, "#E6C25A", "plain", "#E6C25A"),
  K("real sociedad", "#2B5FB8", WHITE, "stripes", WHITE),
  K("sevilla|sevilla fc", WHITE, "#D01F2E", "plain", "#D01F2E"),
  K("valencia|valencia cf", WHITE, BLACK, "plain", BLACK),
  K("villarreal|villarreal cf", "#F2C400", "#1F3FA0", "plain", "#1F3FA0"),
  K("real valladolid|valladolid", "#6B2FB8", WHITE, "plain", WHITE),
  K("las palmas|ud las palmas", "#F2C400", "#1F3FA0", "plain", "#1F3FA0"),
  K("leganes|cd leganes", "#2B5FB8", WHITE, "stripes", WHITE),
  // Bundesliga
  K("fc augsburg|augsburg", "#C8102E", "#1E8E4E", "stripes", WHITE),
  K("union berlin|1 fc union berlin", "#D01F2E", WHITE, "plain", WHITE),
  K("werder bremen", "#1E8E4E", WHITE, "plain", WHITE),
  K("borussia dortmund|dortmund", "#FFD400", BLACK, "plain", BLACK),
  K("eintracht frankfurt|frankfurt", "#0B0F1E", "#D01F2E", "stripes", "#D01F2E"),
  K("sc freiburg|freiburg", "#D01F2E", BLACK, "plain", BLACK),
  K("hamburger sv|hamburg", WHITE, "#2B5FB8", "plain", "#2B5FB8"),
  K("fc heidenheim|heidenheim|1 fc heidenheim", "#D01F2E", "#1F3FA0", "stripes", "#1F3FA0"),
  K("hoffenheim|tsg hoffenheim|1899 hoffenheim", "#2B7FD4", WHITE, "plain", WHITE),
  K("fc koln|koln|cologne|1 fc koln", WHITE, "#D01F2E", "plain", "#D01F2E"),
  K("mainz|mainz 05|fsv mainz 05", "#D01F2E", WHITE, "plain", WHITE),
  K("borussia monchengladbach|monchengladbach|gladbach", WHITE, "#1E8E4E", "plain", "#1E8E4E"),
  K("bayern munich|bayern|fc bayern munchen|bayern munchen", "#D3202E", WHITE, "plain", WHITE),
  K("rb leipzig|leipzig", WHITE, "#D01F2E", "plain", "#1F3FA0"),
  K("st pauli|fc st pauli", "#6B3A1E", WHITE, "plain", WHITE),
  K("vfb stuttgart|stuttgart", WHITE, "#D01F2E", "band", "#D01F2E"),
  K("vfl wolfsburg|wolfsburg", "#6DBE45", WHITE, "plain", WHITE),
  K("bayer leverkusen|leverkusen", "#C8171E", BLACK, "sleeves", BLACK),
  K("vfl bochum|bochum", "#2B5FB8", WHITE, "plain", WHITE),
  K("holstein kiel", "#2B5FB8", WHITE, "stripes", WHITE),
  K("hertha berlin|hertha", WHITE, "#2B5FB8", "plain", "#2B5FB8"),
  // Ligue 1
  K("angers", BLACK, WHITE, "stripes", WHITE),
  K("auxerre", WHITE, "#2B5FB8", "stripes", "#2B5FB8"),
  K("brest|stade brestois|stade brestois 29", "#D01F2E", WHITE, "plain", WHITE),
  K("le havre", "#8FD0F5", "#1F3FA0", "plain", "#1F3FA0"),
  K("lens|rc lens", "#E4B100", "#D01F2E", "stripes", "#D01F2E"),
  K("lille|losc lille", "#D01F2E", "#0B2A6B", "plain", "#0B2A6B"),
  K("lorient|fc lorient", "#F2A900", BLACK, "plain", BLACK),
  K("lyon|olympique lyonnais|olympique lyon", WHITE, "#1F3FA0", "band", "#D01F2E"),
  K("marseille|olympique marseille|olympique de marseille", WHITE, "#41B6E6", "plain", "#41B6E6"),
  K("metz|fc metz", "#7A1B3C", WHITE, "plain", WHITE),
  K("monaco|as monaco", "#D3202E", WHITE, "halves", WHITE),
  K("nantes|fc nantes", "#F2D400", "#1E8E4E", "plain", "#1E8E4E"),
  K("nice|ogc nice", "#D01F2E", BLACK, "stripes", BLACK),
  K("paris fc", "#2B5FB8", WHITE, "plain", WHITE),
  K("paris saint germain|psg|paris sg|paris saint-germain", "#0A1B4B", "#D3202E", "band", "#D3202E"),
  K("rennes|stade rennais", "#D01F2E", BLACK, "stripes", BLACK),
  K("strasbourg|rc strasbourg", "#2B5FB8", WHITE, "plain", WHITE),
  K("toulouse|toulouse fc", "#6B2FB8", WHITE, "plain", WHITE),
  K("reims|stade de reims", "#D01F2E", WHITE, "plain", WHITE),
  K("montpellier", "#F58220", "#1F3FA0", "plain", "#1F3FA0"),
  K("saint etienne|as saint etienne", "#1E8E4E", WHITE, "plain", WHITE),
  K("estac troyes|troyes", "#2B5FB8", WHITE, "plain", WHITE),
  K("bordeaux", "#0A1B4B", WHITE, "plain", WHITE),
];

const NEUTRAL_KIT: ClubKit = { primary: "#5B6AA8", secondary: "#8FA0D8", pattern: "plain", trim: "#FFFFFF" };

export function normalizeClubName(name: string): string {
  return name
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9 ]+/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

const KIT_INDEX: Map<string, ClubKit> = (() => {
  const map = new Map<string, ClubKit>();
  for (const [aliases, primary, secondary, pattern, trim] of CLUB_ROWS) {
    for (const alias of aliases.split("|")) {
      map.set(normalizeClubName(alias), { primary, secondary, pattern, trim });
    }
  }
  return map;
})();

/** Elenco dei club con maglia mappata (nomi normalizzati), per verifiche e test. */
export const KNOWN_CLUB_KEYS: readonly string[] = [...KIT_INDEX.keys()];

const STRIP_WORDS = new Set(["fc", "cf", "afc", "ac", "as", "sc", "ssc", "us", "ud", "cd", "rc", "ca", "ogc", "1", "fsv", "tsg", "vfl", "vfb", "rcd", "sv"]);

/** Maglia del club reale; maglia neutra se il nome non è noto. */
export function clubKit(teamName?: string | null): ClubKit {
  if (!teamName) {
    return NEUTRAL_KIT;
  }
  const key = normalizeClubName(teamName);
  const direct = KIT_INDEX.get(key);
  if (direct) {
    return direct;
  }
  const stripped = key
    .split(" ")
    .filter((word) => !STRIP_WORDS.has(word))
    .join(" ");
  return KIT_INDEX.get(stripped) ?? NEUTRAL_KIT;
}

export function hasClubKit(teamName?: string | null): boolean {
  return clubKit(teamName) !== NEUTRAL_KIT;
}

const SKIN: ReadonlyArray<readonly [string, string]> = [
  ["#F4C6A0", "#D9A074"],
  ["#E9B189", "#C98C61"],
  ["#C98B5F", "#A86B43"],
  ["#9A6240", "#7B4A2D"],
  ["#6E4329", "#52301C"],
];
const HAIR_COLORS = ["#2B1D16", "#4A2E20", "#1A1412", "#8A5A2B"] as const;
const HAIR_STYLES = ["buzz", "crop", "quiff", "curly", "long", "wavy", "side", "crop", "quiff"] as const;
type HairStyle = (typeof HAIR_STYLES)[number];

function hashSeed(seed: string): number {
  let h = 2166136261;
  for (let i = 0; i < seed.length; i += 1) {
    h ^= seed.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return h >>> 0;
}

function rng(seed: number): () => number {
  let a = seed;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

export interface AvatarSpec {
  skin: string;
  skinShade: string;
  hair: HairStyle;
  hairColor: string;
  beard: boolean;
  kit: ClubKit;
}

export function avatarSpec(athleteId: string, teamName?: string | null): AvatarSpec {
  const random = rng(hashSeed(athleteId));
  const pick = <T,>(items: readonly T[]): T => items[Math.floor(random() * items.length)] as T;
  const [skin, skinShade] = pick([SKIN[0], SKIN[0], SKIN[1], SKIN[1], SKIN[2], SKIN[3], SKIN[4]] as const) as readonly [string, string];
  const hair = pick(HAIR_STYLES);
  return {
    skin,
    skinShade,
    hair,
    hairColor: pick(HAIR_COLORS),
    beard: random() < 0.35 && hair !== "long",
    kit: clubKit(teamName),
  };
}

function hairSvg(style: HairStyle, c: string): string {
  switch (style) {
    case "buzz":
      return `<path d="M35.5 37 Q34 20 50 19 Q66 20 64.5 37 Q61 29 50 29 Q39 29 35.5 37Z" fill="${c}"/>`;
    case "crop":
      return `<path d="M34 38 Q31 16 50 15 Q69 16 66 38 Q63 27 54 26 Q44 25 38 29 Q35 32 34 38Z" fill="${c}"/>`;
    case "quiff":
      return `<path d="M33 38 Q28 14 48 12 Q70 11 67 38 Q64 26 56 24 Q46 20 40 27 Q35 31 33 38Z" fill="${c}"/><path d="M44 18 Q52 8 63 15" stroke="${c}" stroke-width="5" fill="none" stroke-linecap="round"/>`;
    case "curly":
      return [[38, 26, 8], [46, 20, 9], [55, 19, 9], [63, 25, 8], [34, 34, 6], [67, 34, 6], [50, 26, 8]]
        .map(([x, y, r]) => `<circle cx="${x}" cy="${y}" r="${r}" fill="${c}"/>`)
        .join("");
    case "long":
      return `<path d="M32 44 Q26 14 50 13 Q74 14 68 44 Q71 58 66 66 Q64 48 62 40 Q56 28 50 28 Q44 28 38 40 Q36 48 34 66 Q29 58 32 44Z" fill="${c}"/>`;
    case "wavy":
      return `<path d="M33 40 Q27 12 50 12 Q73 12 67 40 Q70 52 65 58 Q63 45 60 38 Q52 26 40 32 Q37 36 35 58 Q30 52 33 40Z" fill="${c}"/><path d="M36 22 Q42 14 50 16 Q58 12 64 22" stroke="${c}" stroke-width="4" fill="none"/>`;
    case "side":
      return `<path d="M34 38 Q30 15 50 14 Q68 14 66 38 Q64 28 56 25 Q44 23 38 30 Q35 33 34 38Z" fill="${c}"/>`;
    default:
      return "";
  }
}

function kitBody(kit: ClubKit): string {
  const { secondary: s, pattern } = kit;
  switch (pattern) {
    case "stripes":
      return [14, 32, 50, 68, 86].map((x) => `<rect x="${x - 4}" y="60" width="9" height="50" fill="${s}"/>`).join("");
    case "halves":
      return `<rect x="50" y="60" width="50" height="50" fill="${s}"/>`;
    case "sash":
      return `<polygon points="20,70 38,66 90,110 66,110" fill="${s}"/>`;
    case "sleeves":
      return `<rect x="0" y="60" width="26" height="50" fill="${s}"/><rect x="74" y="60" width="26" height="50" fill="${s}"/>`;
    case "band":
      return `<rect x="0" y="88" width="100" height="9" fill="${s}"/>`;
    case "hoops":
      return [74, 86, 98].map((y) => `<rect x="0" y="${y}" width="100" height="6" fill="${s}"/>`).join("");
    default:
      return "";
  }
}

/** SVG (stringa) dell'avatar tondo, senza anello: l'anello del ruolo lo disegna l'interfaccia. */
export function playerAvatarSvg(athleteId: string, teamName?: string | null): string {
  const spec = avatarSpec(athleteId, teamName);
  const { kit } = spec;
  const uid = `a${hashSeed(`${athleteId}|${teamName ?? ""}`).toString(36)}`;
  const shoulders = "M6 104 Q10 76 34 70 Q50 66 66 70 Q90 76 94 104Z";
  const beard = spec.beard
    ? `<path d="M36 44 Q36 62 50 62 Q64 62 64 44 Q58 54 50 54 Q42 54 36 44Z" fill="${spec.hairColor}" opacity=".55"/>`
    : "";
  return (
    `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><defs><clipPath id="${uid}c"><circle cx="50" cy="50" r="50"/></clipPath><clipPath id="${uid}b"><path d="${shoulders}"/></clipPath></defs>` +
    `<g clip-path="url(#${uid}c)"><rect width="100" height="100" fill="#E3E7F0"/><circle cx="50" cy="40" r="46" fill="#EEF1F8"/>` +
    `<g transform="translate(50 54) scale(1.14) translate(-50 -58)"><path d="${shoulders}" fill="${kit.primary}"/><g clip-path="url(#${uid}b)">${kitBody(kit)}</g>` +
    `<path d="M43 50 L43 72 Q50 80 57 72 L57 50Z" fill="${spec.skinShade}"/>` +
    `<path d="M38 69 L50 84 L62 69 L58 66 L50 76 L42 66Z" fill="${kit.trim}"/>` +
    `<ellipse cx="34" cy="42" rx="3.6" ry="5.5" fill="${spec.skin}"/><ellipse cx="66" cy="42" rx="3.6" ry="5.5" fill="${spec.skin}"/>` +
    `<ellipse cx="50" cy="41" rx="15.5" ry="19.5" fill="${spec.skin}"/>${beard}${hairSvg(spec.hair, spec.hairColor)}</g></g></svg>`
  );
}

/** URL `data:` dell'avatar: si può usare dove prima c'era l'URL della foto (`<img src>`). */
export function playerAvatarUrl(athleteId: string, teamName?: string | null): string {
  return `data:image/svg+xml;utf8,${encodeURIComponent(playerAvatarSvg(athleteId, teamName))}`;
}
