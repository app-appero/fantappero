import type { ScreenTabItem } from "../components/ScreenTabs";
import type { AppTabParamList } from "./types";

/** Rosa/Asta/Svincolati/Mercato: tab condivise per lo screen strip "Mercato" (EP13-P01). */
export const MARKET_HUB_TABS: readonly (ScreenTabItem & { id: keyof AppTabParamList })[] = [
  { id: "Roster", label: "Rosa" },
  { id: "Auction", label: "Asta" },
  { id: "Waiver", label: "Svincolati" },
  { id: "Market", label: "Mercato" },
];
