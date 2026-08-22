import type {
  MarketBidStatus,
  MarketHistoryCategory,
  MarketReleaseReason,
  MarketSessionStatus,
  TradeStatus,
} from "@fantappero/contracts";
import { theme } from "@fantappero/ui/theme";

const { colors } = theme;

/** Shared label/color maps for the market screens (Auction/Waiver/Market) — mirrors web copy. */

export const SESSION_STATUS_LABEL: Record<MarketSessionStatus, string> = {
  scheduled: "Programmata",
  open: "Aperta",
  closed: "Chiusa",
  resolved: "Risolta",
};

export type BadgeColorPair = { background: string; text: string };

export const SESSION_STATUS_COLOR: Record<MarketSessionStatus, BadgeColorPair> = {
  scheduled: { background: colors.backgroundElevated, text: colors.foreground },
  open: { background: colors.success, text: colors.accentContrast },
  closed: { background: colors.warning, text: colors.background },
  resolved: { background: colors.accent, text: colors.accentContrast },
};

export const BID_STATUS_LABEL: Record<MarketBidStatus, string> = {
  submitted: "Inviata",
  expired: "Scaduta",
  won: "Vinta",
  lost: "Persa",
  cancelled: "Ritirata",
};

export const TRADE_STATUS_LABEL: Record<TradeStatus, string> = {
  proposed: "Proposta",
  cancelled: "Annullata",
  expired: "Scaduta",
  accepted: "Accettata",
  rejected: "Rifiutata",
  countered: "Controproposta ricevuta",
  pending_approval: "In attesa di approvazione",
  executed: "Eseguita",
  rejected_by_admin: "Rifiutata dall'amministratore",
};

export const TRADE_STATUS_COLOR: Record<TradeStatus, BadgeColorPair> = {
  proposed: { background: colors.accent, text: colors.accentContrast },
  cancelled: { background: colors.backgroundElevated, text: colors.foreground },
  expired: { background: colors.backgroundElevated, text: colors.foreground },
  accepted: { background: colors.success, text: colors.accentContrast },
  rejected: { background: colors.danger, text: colors.accentContrast },
  countered: { background: colors.warning, text: colors.background },
  pending_approval: { background: colors.warning, text: colors.background },
  executed: { background: colors.success, text: colors.accentContrast },
  rejected_by_admin: { background: colors.danger, text: colors.accentContrast },
};

export const RELEASE_REASON_OPTIONS: Array<{ value: MarketReleaseReason; label: string }> = [
  { value: "voluntary", label: "Svincolo volontario" },
  { value: "league_exit", label: "Uscita dai cinque campionati" },
];

export const HISTORY_CATEGORY_OPTIONS: Array<{ value: MarketHistoryCategory; label: string }> = [
  { value: "acquisto", label: "Acquisto" },
  { value: "svincolo", label: "Svincolo" },
  { value: "scambio", label: "Scambio" },
  { value: "intervento_manuale", label: "Intervento manuale" },
];
