import type { ScreenTabItem } from "../components/ScreenTabs";
import type { AppTabParamList } from "./types";

const SHOW_WAIVER_TAB = false;

/**
 * Rosa/Asta/Svincolati/Scambi: tab condivise per lo screen strip "Mercato" (EP13-P01).
 *
 * La tab "Svincolati" è nascosta (`SHOW_WAIVER_TAB`) e la tab "mercato" mostra
 * solo lo scambio tra squadre — stessa decisione applicata al web, mai
 * propagata al mobile fino ad ora (ADR-0006). Lo screen `Waiver` e il resto
 * del codice restano intatti, solo l'accesso da qui sparisce.
 */
const ALL_MARKET_HUB_TABS: readonly (ScreenTabItem & { id: keyof AppTabParamList })[] = [
  { id: "Roster", label: "Rosa" },
  { id: "Auction", label: "Asta" },
  { id: "Waiver", label: "Svincolati" },
  { id: "Market", label: "Scambi" },
];

export const MARKET_HUB_TABS = ALL_MARKET_HUB_TABS.filter(
  (tab) => tab.id !== "Waiver" || SHOW_WAIVER_TAB,
);
