import type { MarketLiveLotStatus, MarketSessionStatus } from "@fantappero/contracts";
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
