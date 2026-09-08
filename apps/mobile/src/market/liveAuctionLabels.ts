import type { MarketLiveLotStatus, MarketLiveNominationMode, MarketSessionStatus } from "@fantappero/contracts";
import { theme } from "@fantappero/ui/theme";
import type { BadgeColorPair } from "./marketLabels";

const { colors } = theme;

/** Label/color maps for the live-auction screen — mirrors web copy (EP08-09). */

export const LIVE_SESSION_STATUS_LABEL: Record<MarketSessionStatus, string> = {
  scheduled: "Programmata",
  open: "In corso",
  closed: "Chiusa",
  resolved: "Terminata",
};

export const LIVE_SESSION_STATUS_COLOR: Record<MarketSessionStatus, BadgeColorPair> = {
  scheduled: { background: colors.backgroundElevated, text: colors.foreground },
  open: { background: colors.success, text: colors.accentContrast },
  closed: { background: colors.warning, text: colors.background },
  resolved: { background: colors.accent, text: colors.accentContrast },
};

export const LIVE_LOT_STATUS_LABEL: Record<MarketLiveLotStatus, string> = {
  open: "In corso",
  sold: "Aggiudicato",
  passed: "Non assegnato",
  cancelled: "Annullato",
  pending_swap: "In attesa di scambio",
};

// Le 5 modalità di chiamata: due storiche (manual, sequential) più tre nuove
// (turn_based, alphabetical_by_role, random) — mirrors
// `apps/web/src/pages/AuctionLivePage.tsx`.
export const NOMINATION_MODE_SHORT_LABEL: Record<MarketLiveNominationMode, string> = {
  manual: "scelta libera",
  turn_based: "a richiamo (a turno)",
  sequential: "lista prestabilita",
  alphabetical_by_role: "alfabetico per ruolo",
  random: "casuale",
};

export const NOMINATION_MODE_OPTIONS: Array<{ value: MarketLiveNominationMode; label: string }> = [
  { value: "manual", label: "Libera" },
  { value: "turn_based", label: "A richiamo (a turno)" },
  { value: "sequential", label: "Lista prestabilita" },
  { value: "alphabetical_by_role", label: "Alfabetico per ruolo" },
  { value: "random", label: "Casuale" },
];

export const NOMINATION_MODE_HINT: Record<MarketLiveNominationMode, string> = {
  manual:
    "L'amministratore (o il delegato) sceglie liberamente, in qualsiasi momento della sessione, quale calciatore mettere all'asta.",
  turn_based:
    "A ogni chiamata tocca a un fantallenatore diverso: l'ordine di turno viene estratto a sorte all'avvio della sessione e si ripete ciclicamente finché la sessione è aperta. L'admin/delegato può comunque chiamare in ogni momento.",
  sequential:
    "Prepari tu l'elenco esatto e ordinato dei calciatori: verranno chiamati automaticamente uno dopo l'altro, nell'ordine scelto qui sotto.",
  alphabetical_by_role:
    "I calciatori liberi vengono chiamati automaticamente in ordine alfabetico, raggruppati per ruolo: prima i portieri, poi difensori, centrocampisti e attaccanti.",
  random:
    "I calciatori liberi vengono chiamati automaticamente in un ordine casuale, estratto una sola volta all'avvio della sessione.",
};

// Modalità che generano da sole la coda di chiamata (nessun elenco da compilare).
export const AUTO_QUEUE_MODES: MarketLiveNominationMode[] = [
  "sequential",
  "alphabetical_by_role",
  "random",
];

