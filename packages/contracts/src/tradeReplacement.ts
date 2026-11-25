/**
 * Sostituto dopo uno scambio sbilanciato (1.5, decisione del 25/11): tipi delle API e testi
 * comuni a sito e app.
 *
 * Uno scambio che lascia una squadra sotto la misura della rosa (es. 2 per 1: 34/35) le dà il
 * diritto di comprare subito, anche a mercato chiuso, un calciatore libero del ruolo che manca,
 * al suo Valore. Le regole sono del server (`backend/src/market/trade_replacement.py`): qui ci
 * sono solo i testi e i conti mostrati, con i numeri, i ruoli e i plurali dei dati veri.
 *
 * Solo logica pura e import di tipo: i test `node:test` (anche quelli dell'app) caricano il file
 * dal sorgente.
 */
import type { AthleteSeasonAverage } from "./athleteValue.js";
import type { FantasyRole, FantasyTeam, RosterUnderQuotaRole } from "./leagues.js";

export type { RosterUnderQuotaRole } from "./leagues.js";

/** Un ruolo da scegliere come sostituto e quanti. */
export interface TradeMissingRole {
  role: FantasyRole;
  count: number;
}

/**
 * Quanto costano i sostituti di un ruolo che manca, ai prezzi dei liberi di adesso: stesso prezzo
 * dell'acquisto (il Valore, il minimo dove manca) e stessi liberi (non impegnati in aste o
 * svincolati aperti).
 */
export interface TradeReplacementCost {
  role: FantasyRole;
  count: number;
  /** Il libero più economico del ruolo; `null` se non c'è nessun libero. */
  cheapestPrice: number | null;
  /** I `count` liberi più economici insieme; `null` se non ce ne sono abbastanza. */
  totalPrice: number | null;
}

/**
 * Come resterebbe la rosa di una squadra dopo lo scambio (campo `proposerRosterAfter` /
 * `recipientRosterAfter` delle proposte aperte e dell'anteprima). `missingRoles` sono i sostituti
 * da scegliere subito dopo: vuoto se la rosa resta alla misura.
 *
 * I campi facoltativi sono arrivati dopo la corsa Mercato del 25/11 (assenti sui server più
 * vecchi): crediti dopo lo scambio, prezzo più basso dei sostituti e se bastano, ruoli sotto quota.
 */
export interface TradeRosterAfter {
  teamId: string;
  teamName: string;
  sizeAfter: number;
  rosterSize: number;
  missingRoles: TradeMissingRole[];
  /** Crediti dopo lo scambio, con i crediti offerti o chiesti. */
  balanceAfter?: number;
  replacementCosts?: TradeReplacementCost[];
  /** `false`: da sola non potrà prendere i sostituti (dovrà assegnarli l'admin). Solo un avviso. */
  canAffordReplacement?: boolean;
  /** Ruoli sotto la quota della lega subito dopo lo scambio (prima dei sostituti). */
  underQuotaRoles?: RosterUnderQuotaRole[];
}

/** Bozza da valutare prima di inviare una proposta o una controproposta. */
export interface TradePreviewRequest {
  recipientTeamId: string;
  offeredAthleteIds: string[];
  requestedAthleteIds: string[];
  /** Crediti offerti e chiesti, per i crediti dopo lo scambio (facoltativi). */
  offeredCredits?: number;
  requestedCredits?: number;
}

export interface TradePreview {
  proposerRosterAfter: TradeRosterAfter;
  recipientRosterAfter: TradeRosterAfter;
}

export interface TradeReplacementPending {
  id: string;
  role: FantasyRole;
  tradeProposalId: string;
  createdAt: string;
}

/** `GET …/mercato/sostituti`: i sostituti che la mia squadra deve scegliere. */
export interface TradeReplacementStatus {
  teamId: string;
  rosterSize: number;
  filledSlots: number;
  balance: number;
  pending: TradeReplacementPending[];
  missingRoles: TradeMissingRole[];
  tradeProposalId: string | null;
  otherTeamName: string | null;
  receivedAthleteNames: string[];
  receivedCredits: number;
  /** `round_in_progress`: le rose sono ferme fino al calcolo del turno. */
  blockedReason: "round_in_progress" | null;
  blockedMessage: string | null;
  /** `false`: con i crediti di adesso non può prendere da sola i sostituti (server dopo il 25/11). */
  canAffordReplacement?: boolean;
  /** Il libero più economico fra i ruoli che mancano; `null` senza sostituti o senza liberi. */
  cheapestReplacementPrice?: number | null;
  replacementCosts?: TradeReplacementCost[];
  /** Ruoli sotto la quota della lega nella rosa di adesso. */
  underQuotaRoles?: RosterUnderQuotaRole[];
}

export interface TradeReplacementCandidate {
  athleteId: string;
  name: string;
  photoUrl: string | null;
  clubName: string | null;
  role: FantasyRole;
  /** Il Valore del calciatore in questa lega: è il prezzo del sostituto. */
  marketValue: number;
  seasonAverage: AthleteSeasonAverage | null;
  /** `false` se costa più dei crediti rimasti. */
  affordable: boolean;
}

export interface TradeReplacementCandidateList {
  role: FantasyRole;
  balance: number;
  total: number;
  candidates: TradeReplacementCandidate[];
}

/** Ordine dell'elenco dei liberi: per Valore (dal più alto o dal più basso) o per nome. */
export type TradeReplacementOrder = "valore" | "valore-crescente" | "nome";

export interface TradeReplacementCandidateQuery {
  role?: FantasyRole;
  search?: string;
  order?: TradeReplacementOrder;
}

export interface TradeReplacementPurchaseRequest {
  athleteId: string;
}

export interface TradeReplacementPurchase {
  athleteId: string;
  athleteName: string;
  role: FantasyRole;
  priceCredits: number;
  balance: number;
  status: TradeReplacementStatus;
}

const ROLE_NOUN: Record<FantasyRole, readonly [string, string]> = {
  P: ["Portiere", "Portieri"],
  D: ["Difensore", "Difensori"],
  C: ["Centrocampista", "Centrocampisti"],
  A: ["Attaccante", "Attaccanti"],
};

const ROLE_ORDER: readonly FantasyRole[] = ["P", "D", "C", "A"];

/** «Difensore». */
export function roleSingularLabel(role: FantasyRole): string {
  return ROLE_NOUN[role][0];
}

/** «1 Difensore» / «2 Difensori». */
export function roleCountLabel(role: FantasyRole, count: number): string {
  const [one, many] = ROLE_NOUN[role];
  return `${count} ${count === 1 ? one : many}`;
}

/** Quanti sostituti in tutto. */
export function missingRolesTotal(missing: readonly TradeMissingRole[] | null | undefined): number {
  return (missing ?? []).reduce((sum, item) => sum + Math.max(0, item.count), 0);
}

function normalized(missing: readonly TradeMissingRole[] | null | undefined): TradeMissingRole[] {
  const counts = new Map<FantasyRole, number>();
  for (const item of missing ?? []) {
    if (item.count > 0) {
      counts.set(item.role, (counts.get(item.role) ?? 0) + item.count);
    }
  }
  return ROLE_ORDER.filter((role) => counts.has(role)).map((role) => ({ role, count: counts.get(role) ?? 0 }));
}

/** «1 Difensore», «2 Difensori», «1 Difensore e 1 Centrocampista». */
export function missingRolesLabel(missing: readonly TradeMissingRole[] | null | undefined): string {
  const parts = normalized(missing).map((item) => roleCountLabel(item.role, item.count));
  if (parts.length <= 1) {
    return parts[0] ?? "";
  }
  return `${parts.slice(0, -1).join(", ")} e ${parts[parts.length - 1]}`;
}

/** «un Difensore» con un solo sostituto, altrimenti come `missingRolesLabel`. */
function missingWithArticle(missing: readonly TradeMissingRole[]): string {
  const items = normalized(missing);
  if (items.length === 1 && items[0]?.count === 1) {
    return `un ${roleSingularLabel(items[0].role)}`;
  }
  return missingRolesLabel(items);
}

/** «1 credito» / «12 crediti». */
export function creditsLabel(credits: number): string {
  return credits === 1 ? "1 credito" : `${credits} crediti`;
}

// -- Avviso prima dello scambio -------------------------------------------------

/** Chi vede l'avviso: chi accetta, chi propone o l'amministratore che approva. */
export type TradeShortfallAudience = "accept" | "propose" | "approve";

export interface TradeShortfallWarning {
  /** «Dopo lo scambio avrai 34/35» (all'admin: «Dopo lo scambio Squadra X avrà 34/35»). */
  title: string;
  body: string;
}

/** Pulsanti della conferma di uno scambio che lascia la rosa corta. */
export const TRADE_SHORTFALL_CANCEL_LABEL = "Annulla";
export const TRADE_SHORTFALL_ACCEPT_LABEL = "Accetta e scegli";
export const TRADE_SHORTFALL_PROPOSE_LABEL = "Proponi scambio";
export const TRADE_SHORTFALL_APPROVE_LABEL = "Approva";
/** Titolo della conferma per chi propone e per l'amministratore (chi accetta ha già la sua). */
export const TRADE_SHORTFALL_PROPOSE_TITLE = "Proporre lo scambio?";
export const TRADE_SHORTFALL_APPROVE_TITLE = "Approvare lo scambio?";
/** Stessa conferma nella controproposta (corsa Mercato del 25/11): titolo e pulsante suoi. */
export const TRADE_SHORTFALL_COUNTER_TITLE = "Inviare la controproposta?";
export const TRADE_SHORTFALL_COUNTER_LABEL = "Invia controproposta";

/** Titolo e pulsante della conferma prima di inviare: proposta nuova o controproposta. */
export function tradeProposeConfirmCopy(kind: "propose" | "counter"): { title: string; label: string } {
  return kind === "counter"
    ? { title: TRADE_SHORTFALL_COUNTER_TITLE, label: TRADE_SHORTFALL_COUNTER_LABEL }
    : { title: TRADE_SHORTFALL_PROPOSE_TITLE, label: TRADE_SHORTFALL_PROPOSE_LABEL };
}

/**
 * Il riquadro arancione «Dopo lo scambio avrai 34/35» per una squadra che resterà sotto la misura
 * della rosa; `null` se non deve scegliere sostituti (rosa alla misura, o corta per altri motivi,
 * che non danno diritto al sostituto).
 */
export function tradeShortfallWarning(
  after: TradeRosterAfter | null | undefined,
  audience: TradeShortfallAudience,
): TradeShortfallWarning | null {
  if (!after) {
    return null;
  }
  const total = missingRolesTotal(after.missingRoles);
  if (total === 0) {
    return null;
  }
  const many = total > 1;
  const missing = missingWithArticle(after.missingRoles);
  const size = `${after.sizeAfter}/${after.rosterSize}`;
  const it = many ? "li" : "lo";
  const value = many ? "al loro Valore" : "al suo Valore";
  if (audience === "approve") {
    return {
      title: `Dopo lo scambio ${after.teamName} avrà ${size}`,
      body:
        `${many ? "Le mancheranno" : "Le mancherà"} ${missing}. Appena approvi dovrà ` +
        `sceglier${it} dagli svincolati, ${value}. Finché non ${it} sceglie non potrà schierare ` +
        "la formazione.",
    };
  }
  const when = audience === "accept" ? "Appena accetti" : "Se lo scambio viene accettato";
  return {
    title: `Dopo lo scambio avrai ${size}`,
    body:
      `${many ? "Ti mancheranno" : "Ti mancherà"} ${missing}. ${when} dovrai sceglier${it} ` +
      `dagli svincolati, ${value}. Finché non ${it} scegli non potrai schierare la formazione.`,
  };
}

type RosterAfterProposal = {
  proposerTeamId: string;
  recipientTeamId: string;
  proposerRosterAfter?: TradeRosterAfter | null;
  recipientRosterAfter?: TradeRosterAfter | null;
};

/** La rosa dopo lo scambio della mia squadra, se sono una delle due parti. */
export function myRosterAfter(
  proposal: RosterAfterProposal,
  myTeamId: string | null | undefined,
): TradeRosterAfter | null {
  if (!myTeamId) {
    return null;
  }
  if (proposal.recipientTeamId === myTeamId) {
    return proposal.recipientRosterAfter ?? null;
  }
  if (proposal.proposerTeamId === myTeamId) {
    return proposal.proposerRosterAfter ?? null;
  }
  return null;
}

/** Per l'amministratore: le squadre che lo scambio lascerà corte (con i sostituti da scegliere). */
export function shortRostersAfter(proposal: RosterAfterProposal): TradeRosterAfter[] {
  return [proposal.proposerRosterAfter, proposal.recipientRosterAfter].filter(
    (after): after is TradeRosterAfter => Boolean(after) && missingRolesTotal(after?.missingRoles) > 0,
  );
}

// -- Crediti che non bastano per il sostituto (corsa Mercato del 25/11) ----------

/** Articolo determinativo del ruolo al singolare: «il Difensore», «l'Attaccante». */
const ROLE_ARTICLE: Record<FantasyRole, string> = { P: "il ", D: "il ", C: "il ", A: "l'" };

/** «il Difensore», «i 2 Difensori», «il Difensore e il Centrocampista». */
function rolesWithArticle(costs: readonly TradeReplacementCost[]): string {
  const parts = costs.map((cost) =>
    cost.count === 1 ? `${ROLE_ARTICLE[cost.role]}${roleSingularLabel(cost.role)}` : `i ${roleCountLabel(cost.role, cost.count)}`,
  );
  if (parts.length <= 1) {
    return parts[0] ?? "";
  }
  return `${parts.slice(0, -1).join(", ")} e ${parts[parts.length - 1]}`;
}

function orderedCosts(costs: readonly TradeReplacementCost[] | null | undefined): TradeReplacementCost[] {
  return [...(costs ?? [])]
    .filter((cost) => cost.count > 0)
    .sort((left, right) => ROLE_ORDER.indexOf(left.role) - ROLE_ORDER.indexOf(right.role));
}

/**
 * «Attenzione: dopo lo scambio avrai 0 crediti e il Difensore libero più economico costa 8. Da solo
 * non potrai prendere il sostituto: dovrà assegnartelo l'admin.» (all'admin in terza persona, con
 * il nome della squadra). `null` se i crediti bastano, se non mancano giocatori o se il server non
 * manda i prezzi (più vecchio, o nessun libero del ruolo). Solo un avviso: lo scambio non si blocca.
 */
export function tradeCreditsWarning(
  after: TradeRosterAfter | null | undefined,
  audience: TradeShortfallAudience,
): string | null {
  if (!after || after.canAffordReplacement !== false || typeof after.balanceAfter !== "number") {
    return null;
  }
  const total = missingRolesTotal(after.missingRoles);
  const costs = orderedCosts(after.replacementCosts);
  if (total === 0 || costs.length === 0 || costs.some((cost) => cost.totalPrice === null)) {
    return null;
  }
  const many = costs.reduce((sum, cost) => sum + cost.count, 0) > 1;
  const price = costs.reduce((sum, cost) => sum + (cost.totalPrice ?? 0), 0);
  const credits = creditsLabel(Math.max(0, after.balanceAfter));
  const cheapest = many
    ? `${rolesWithArticle(costs)} liberi più economici costano ${price} in tutto`
    : `${rolesWithArticle(costs)} libero più economico costa ${price}`;
  const what = many ? "i sostituti" : "il sostituto";
  if (audience === "approve") {
    return (
      `Attenzione: dopo lo scambio ${after.teamName} avrà ${credits} e ${cheapest}. ` +
      `Da sola non potrà prendere ${what}: dovrà ${many ? "assegnarglieli" : "assegnarglielo"} l'admin.`
    );
  }
  return (
    `Attenzione: dopo lo scambio avrai ${credits} e ${cheapest}. ` +
    `Da solo non potrai prendere ${what}: dovrà ${many ? "assegnarteli" : "assegnartelo"} l'admin.`
  );
}

// -- Ruoli sotto quota con la rosa piena (corsa Mercato del 25/11) ----------------

/** I ruoli davvero sotto quota, nell'ordine P, D, C, A. */
function normalizedUnderQuota(items: readonly RosterUnderQuotaRole[] | null | undefined): RosterUnderQuotaRole[] {
  return ROLE_ORDER.flatMap((role) =>
    (items ?? []).filter((item) => item.role === role && item.count < item.quota).slice(0, 1),
  );
}

/** «9 Centrocampisti su 11», «2 Portieri su 3 e 9 Centrocampisti su 11». */
export function underQuotaLabel(items: readonly RosterUnderQuotaRole[] | null | undefined): string {
  const parts = normalizedUnderQuota(items).map((item) => `${roleCountLabel(item.role, item.count)} su ${item.quota}`);
  if (parts.length <= 1) {
    return parts[0] ?? "";
  }
  return `${parts.slice(0, -1).join(", ")} e ${parts[parts.length - 1]}`;
}

/** I ruoli sotto quota dopo aver preso un calciatore del ruolo `role`. */
export function underQuotaAfterPurchase(
  items: readonly RosterUnderQuotaRole[] | null | undefined,
  role: FantasyRole,
): RosterUnderQuotaRole[] {
  return normalizedUnderQuota(items)
    .map((item) => (item.role === role ? { ...item, count: item.count + 1 } : item))
    .filter((item) => item.count < item.quota);
}

/**
 * I ruoli che restano sotto quota anche dopo i sostituti: a ogni ruolo sotto quota si aggiungono
 * i sostituti dello stesso ruolo da scegliere subito dopo lo scambio.
 */
export function underQuotaAfterReplacements(after: TradeRosterAfter | null | undefined): RosterUnderQuotaRole[] {
  if (!after) {
    return [];
  }
  const covered = new Map(normalized(after.missingRoles).map((item) => [item.role, item.count]));
  return normalizedUnderQuota(after.underQuotaRoles)
    .map((item) => ({ ...item, count: item.count + (covered.get(item.role) ?? 0) }))
    .filter((item) => item.count < item.quota);
}

/**
 * Riga informativa prima dello scambio: «Dopo lo scambio avrai 9 Centrocampisti su 11.». Se mancano
 * anche giocatori dice che il ruolo resta sotto quota pure con i sostituti («Anche con il sostituto
 * avrai 10 Centrocampisti su 11.»); all'admin con il nome della squadra. `null` se nessun ruolo
 * resta sotto quota, o se la rosa resterà corta per altri motivi (lì l'avviso dei ruoli non aiuta).
 */
export function tradeQuotaNote(
  after: TradeRosterAfter | null | undefined,
  audience: TradeShortfallAudience,
): string | null {
  if (!after) {
    return null;
  }
  const missing = missingRolesTotal(after.missingRoles);
  if (after.sizeAfter + missing < after.rosterSize) {
    return null;
  }
  const label = underQuotaLabel(underQuotaAfterReplacements(after));
  if (!label) {
    return null;
  }
  const subject = audience === "approve" ? `${after.teamName} avrà` : "avrai";
  if (missing === 0) {
    return `Dopo lo scambio ${subject} ${label}.`;
  }
  return `Anche ${missing > 1 ? "con i sostituti" : "con il sostituto"} ${subject} ${label}.`;
}

/**
 * Tutto quello che va detto prima dello scambio su una squadra: il riquadro arancione «Dopo lo
 * scambio avrai 34/35» (con l'avviso dei crediti se non bastano) e la riga dei ruoli sotto quota.
 * Senza giocatori mancanti la riga dei ruoli va da sola in un riquadro giallo più leggero (`info`).
 */
export interface TradeAfterNotice {
  /** `warning`: mancano giocatori (arancione); `info`: solo ruoli sotto quota (giallo leggero). */
  tone: "warning" | "info";
  title: string | null;
  body: string | null;
  /** «Attenzione: dopo lo scambio avrai N crediti…», solo con `warning`. */
  creditsWarning: string | null;
  /** «Dopo lo scambio avrai 9 Centrocampisti su 11.» */
  quotaNote: string | null;
}

export function tradeAfterNotice(
  after: TradeRosterAfter | null | undefined,
  audience: TradeShortfallAudience,
): TradeAfterNotice | null {
  const shortfall = tradeShortfallWarning(after, audience);
  const quotaNote = tradeQuotaNote(after, audience);
  if (!shortfall && !quotaNote) {
    return null;
  }
  return {
    tone: shortfall ? "warning" : "info",
    title: shortfall?.title ?? null,
    body: shortfall?.body ?? null,
    creditsWarning: shortfall ? tradeCreditsWarning(after, audience) : null,
    quotaNote,
  };
}

/** Per l'amministratore che approva: gli avvisi delle due squadre (vuoto se non c'è niente da dire). */
export function approveTradeNotices(proposal: RosterAfterProposal): TradeAfterNotice[] {
  return [proposal.proposerRosterAfter, proposal.recipientRosterAfter]
    .map((after) => tradeAfterNotice(after, "approve"))
    .filter((notice): notice is TradeAfterNotice => notice !== null);
}

/** Chiave stabile di un avviso in un elenco (titolo o riga dei ruoli, con il nome della squadra). */
export function tradeAfterNoticeKey(notice: TradeAfterNotice): string {
  return notice.title ?? notice.quotaNote ?? notice.body ?? "";
}

/** Il riquadro «Ruoli sotto quota» in Rosa: testo per una rosa alla misura, `null` altrimenti. */
export const ROSTER_UNDER_QUOTA_HINT = "Puoi completarli con uno scambio o agli svincolati.";

/**
 * «Ruoli sotto quota: 9 Centrocampisti su 11. Puoi completarli con uno scambio o agli svincolati.»
 * Solo con la rosa alla misura (con la rosa corta ci sono già gli altri avvisi, e durante l'asta i
 * ruoli sono tutti sotto quota); `null` se nessun ruolo è sotto quota. Non blocca niente.
 */
export function rosterUnderQuotaNotice(
  roster:
    | { filledSlots: number; rosterSize: number; underQuotaRoles?: readonly RosterUnderQuotaRole[] | null }
    | null
    | undefined,
): string | null {
  if (!roster || roster.rosterSize <= 0 || roster.filledSlots < roster.rosterSize) {
    return null;
  }
  const label = underQuotaLabel(roster.underQuotaRoles);
  return label ? `Ruoli sotto quota: ${label}. ${ROSTER_UNDER_QUOTA_HINT}` : null;
}

/** Lo stesso riquadro dalla squadra letta in Rosa (`GET …/rosa`, `composition.underQuotaRoles`). */
export function teamUnderQuotaNotice(
  team: Pick<FantasyTeam, "filledSlots" | "rosterSize" | "composition"> | null | undefined,
): string | null {
  const composition = team?.composition;
  if (!team || !composition) {
    return null;
  }
  return rosterUnderQuotaNotice({
    filledSlots: team.filledSlots,
    rosterSize: composition.limits?.rosterSize ?? team.rosterSize,
    underQuotaRoles: composition.underQuotaRoles,
  });
}

// -- Finestra «Scegli il sostituto» ---------------------------------------------

export const REPLACEMENT_SHEET_TITLE = "Scegli il sostituto";
export const REPLACEMENT_LATER_LABEL = "Più tardi";
export const REPLACEMENT_LATER_NOTE = "Finché non scegli non puoi schierare la formazione.";
export const REPLACEMENT_TOO_EXPENSIVE = "Costa più dei tuoi crediti";
export const REPLACEMENT_SEARCH_PLACEHOLDER = "Cerca per nome o squadra";
export const REPLACEMENT_CONFIRM_LABEL = "Conferma";
export const REPLACEMENT_CANCEL_LABEL = "Annulla";
export const REPLACEMENT_EMPTY_LIST = "Nessun calciatore libero di questo ruolo.";
/** Sotto «Salva formazione» (disattivato) quando manca il sostituto. */
export const REPLACEMENT_AUTO_LINEUP_NOTE = "Se non scegli entro il blocco, gioca la formazione automatica.";

/** Le scelte dell'ordine nella finestra: il Valore prima (il prezzo). */
export const REPLACEMENT_ORDER_OPTIONS: readonly { value: TradeReplacementOrder; label: string }[] = [
  { value: "valore", label: "Valore più alto" },
  { value: "valore-crescente", label: "Valore più basso" },
  { value: "nome", label: "Nome" },
];

type ReplacementStatusLike = Pick<
  TradeReplacementStatus,
  "pending" | "missingRoles" | "filledSlots" | "rosterSize"
> &
  Partial<
    Pick<TradeReplacementStatus, "tradeProposalId" | "receivedAthleteNames" | "receivedCredits" | "balance" | "underQuotaRoles">
  >;

/** Ci sono sostituti da scegliere. */
export function hasPendingReplacement(status: Pick<TradeReplacementStatus, "pending"> | null | undefined): boolean {
  return (status?.pending.length ?? 0) > 0;
}

function namesList(names: readonly string[]): string {
  if (names.length <= 1) {
    return names[0] ?? "";
  }
  return `${names.slice(0, -1).join(", ")} e ${names[names.length - 1]}`;
}

/** Il riquadro verde in alto: «Scambio fatto: è arrivato N. Zortea». */
export function replacementDoneBanner(status: ReplacementStatusLike | null | undefined): string | null {
  if (!status?.tradeProposalId) {
    return null;
  }
  const names = (status.receivedAthleteNames ?? []).map((name) => name.trim()).filter(Boolean);
  if (names.length === 1) {
    return `Scambio fatto: è arrivato ${names[0]}`;
  }
  if (names.length > 1) {
    return `Scambio fatto: sono arrivati ${namesList(names)}`;
  }
  const credits = status.receivedCredits ?? 0;
  return credits > 0 ? `Scambio fatto: hai ricevuto ${creditsLabel(credits)}` : "Scambio fatto";
}

/** «Ti manca 1 Difensore. Scegline uno tra i liberi: lo paghi il suo Valore.» */
export function replacementIntro(missing: readonly TradeMissingRole[] | null | undefined): string {
  const total = missingRolesTotal(missing);
  if (total === 0) {
    return "";
  }
  if (total === 1) {
    return `Ti manca ${missingRolesLabel(missing)}. Scegline uno tra i liberi: lo paghi il suo Valore.`;
  }
  return `Ti mancano ${missingRolesLabel(missing)}. Scegline uno alla volta tra i liberi: lo paghi il suo Valore.`;
}

/** Le tre etichette sotto il testo: «Rosa 34/35», «Crediti N», «Solo D». */
export function replacementChips(
  status: Pick<TradeReplacementStatus, "filledSlots" | "rosterSize" | "balance">,
  role: FantasyRole,
): string[] {
  return [`Rosa ${status.filledSlots}/${status.rosterSize}`, `Crediti ${status.balance}`, `Solo ${role}`];
}

/** I ruoli fra cui scegliere, nell'ordine P, D, C, A (uno solo nel caso tipico). */
export function replacementRoles(missing: readonly TradeMissingRole[] | null | undefined): FantasyRole[] {
  return normalized(missing).map((item) => item.role);
}

/** Pulsante di una riga dell'elenco: «Prendi · 12». */
export function replacementTakeLabel(price: number): string {
  return `Prendi · ${price}`;
}

/** «Prendi N. Zortea per 12 crediti?» */
export function replacementConfirmTitle(name: string, price: number): string {
  return `Prendi ${name} per ${creditsLabel(price)}?`;
}

export interface ReplacementCreditRow {
  label: string;
  value: string;
  /** La riga del totale («Ti restano»). */
  total?: boolean;
}

/** Il conto: «Crediti ora», «Valore di <nome> − N», «Ti restano». */
export function replacementCreditRows(balance: number, name: string, price: number): ReplacementCreditRow[] {
  return [
    { label: "Crediti ora", value: String(balance) },
    { label: `Valore di ${name}`, value: `− ${price}` },
    { label: "Ti restano", value: String(balance - price), total: true },
  ];
}

/** Crediti dopo l'acquisto. */
export function creditsAfterReplacement(balance: number, price: number): number {
  return balance - price;
}

/** I sostituti che restano da scegliere dopo aver preso un calciatore del ruolo `role`. */
export function missingAfterPurchase(
  missing: readonly TradeMissingRole[] | null | undefined,
  role: FantasyRole,
): TradeMissingRole[] {
  let taken = false;
  return normalized(missing)
    .map((item) => {
      if (!taken && item.role === role) {
        taken = true;
        return { role: item.role, count: item.count - 1 };
      }
      return item;
    })
    .filter((item) => item.count > 0);
}

/**
 * Sotto il conto: «La rosa torna 35/35 e puoi schierare subito la formazione. Vale anche a
 * mercato chiuso.»; se restano altri sostituti da scegliere lo dice.
 */
export function replacementConfirmNote(status: ReplacementStatusLike, role: FantasyRole): string {
  const after = status.filledSlots + 1;
  const left = missingAfterPurchase(status.missingRoles, role);
  if (left.length === 0 && after >= status.rosterSize) {
    const base = `La rosa torna ${after}/${status.rosterSize} e puoi schierare subito la formazione. Vale anche a mercato chiuso.`;
    // Ultimo sostituto: se un ruolo resta sotto quota lo dice già qui (corsa Mercato del 25/11).
    const quota = rosterUnderQuotaNotice({
      filledSlots: after,
      rosterSize: status.rosterSize,
      underQuotaRoles: underQuotaAfterPurchase(status.underQuotaRoles, role),
    });
    return quota ? `${base} ${quota}` : base;
  }
  if (left.length === 0) {
    return `La rosa sale a ${after}/${status.rosterSize}. Vale anche a mercato chiuso.`;
  }
  return `La rosa sale a ${after}/${status.rosterSize}: poi ti resta da scegliere ${missingRolesLabel(left)}. Vale anche a mercato chiuso.`;
}

/** Avviso dopo l'acquisto (toast). */
export function replacementPurchasedMessage(purchase: Pick<TradeReplacementPurchase, "athleteName" | "priceCredits" | "status">): string {
  const left = missingRolesTotal(purchase.status.missingRoles);
  const head = `Hai preso ${purchase.athleteName} per ${creditsLabel(purchase.priceCredits)}.`;
  if (left > 0) {
    return `${head} Ti resta da scegliere ${missingRolesLabel(purchase.status.missingRoles)}.`;
  }
  const done = `${head} La rosa è completa: puoi schierare la formazione.`;
  // Fine della finestra: un ruolo ancora sotto quota (dato del server dopo l'acquisto).
  const quota = rosterUnderQuotaNotice(purchase.status);
  return quota ? `${done} ${quota}` : done;
}

/**
 * Riquadro in alto nella finestra quando nessun libero del ruolo è alla portata: «Nessun libero alla
 * tua portata: hai 0 crediti e il più economico costa 8. Chiedi all'admin di assegnarti un
 * Difensore.». L'elenco resta visibile (tutto grigio). `null` se il più economico si può prendere o
 * se il server non manda i prezzi.
 */
export function replacementUnaffordableNotice(
  status:
    | (Pick<TradeReplacementStatus, "balance" | "missingRoles"> &
        Partial<Pick<TradeReplacementStatus, "replacementCosts" | "cheapestReplacementPrice">>)
    | null
    | undefined,
  role: FantasyRole | null | undefined,
): string | null {
  if (!status || !role) {
    return null;
  }
  const cost = status.replacementCosts?.find((item) => item.role === role);
  const cheapest = cost ? cost.cheapestPrice : (status.cheapestReplacementPrice ?? null);
  if (cheapest === null || cheapest <= status.balance) {
    return null;
  }
  const count = normalized(status.missingRoles).find((item) => item.role === role)?.count ?? cost?.count ?? 1;
  const who = count === 1 ? `un ${roleSingularLabel(role)}` : roleCountLabel(role, count);
  return (
    `Nessun libero alla tua portata: hai ${creditsLabel(Math.max(0, status.balance))} e il più economico ` +
    `costa ${cheapest}. Chiedi all'admin di assegnarti ${who}.`
  );
}

// -- Riquadro in Rosa e Formazione ----------------------------------------------

export interface ReplacementBanner {
  /** «Rosa incompleta: 34/35». */
  title: string;
  /** «Ti manca un Difensore dopo lo scambio. Sceglilo per poter schierare la formazione.» */
  body: string;
  /** «Scegli il sostituto (Difensore)». */
  action: string;
  /** Turno in corso: si sceglie dopo il calcolo (messaggio del server), il pulsante resta. */
  blockedMessage: string | null;
}

export function replacementBanner(
  status: (ReplacementStatusLike & Partial<Pick<TradeReplacementStatus, "blockedMessage">>) | null | undefined,
): ReplacementBanner | null {
  if (!status || !hasPendingReplacement(status)) {
    return null;
  }
  const total = missingRolesTotal(status.missingRoles);
  const roles = replacementRoles(status.missingRoles);
  const first = status.pending[0]?.role ?? roles[0] ?? "D";
  const many = total > 1;
  return {
    title: `Rosa incompleta: ${status.filledSlots}/${status.rosterSize}`,
    body: many
      ? `Ti mancano ${missingRolesLabel(status.missingRoles)} dopo lo scambio. Sceglili per poter schierare la formazione.`
      : `Ti manca ${missingWithArticle(status.missingRoles)} dopo lo scambio. Sceglilo per poter schierare la formazione.`,
    action: `Scegli il sostituto (${roleSingularLabel(first)})`,
    blockedMessage: status.blockedMessage ?? null,
  };
}

// -- Apertura automatica, una volta per sessione --------------------------------

/** Chiave di sessione: «Più tardi» non riapre la finestra fino alla sessione dopo. */
export function replacementPromptStorageKey(leagueId: string): string {
  return `fa.sostituto.rimandato.${leagueId}`;
}

/** La finestra si apre da sola se c'è da scegliere e non è già stata rimandata in sessione. */
export function shouldAutoOpenReplacement(
  status: Pick<TradeReplacementStatus, "pending"> | null | undefined,
  alreadyShownThisSession: boolean,
): boolean {
  return hasPendingReplacement(status) && !alreadyShownThisSession;
}
