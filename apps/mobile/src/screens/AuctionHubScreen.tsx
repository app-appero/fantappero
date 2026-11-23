import { useNavigation, useRoute, type NavigationProp, type RouteProp } from "@react-navigation/core";
import { useEffect, useState } from "react";
import { ScreenTabs } from "../components/ScreenTabs";
import { UiStatePanel } from "../components/UiStatePanel";
import { PageContainer } from "../layout/PageContainer";
import { MARKET_HUB_TABS } from "../navigation/marketHubTabs";
import type { AppTabParamList } from "../navigation/types";
import { MarketGateBar } from "../market/MarketGateBar";
import { useAuthSession } from "../session/DemoSessionContext";
import { AuctionLiveScreen } from "./AuctionLiveScreen";
import { AuctionScreen } from "./AuctionScreen";
import { auctionHubHasLeague, auctionModeFromParams, type AuctionMode } from "./auctionMode";

const AUCTION_MODE_TABS = [
  { id: "buste", label: "Buste chiuse" },
  { id: "live", label: "Live" },
] as const;

/**
 * Asta: contenitore con la screen-tabs strip del market hub (Rosa/Asta/…) e,
 * al suo interno, il toggle "Buste chiuse"/"Live" tra `AuctionScreen` (sealed)
 * e `AuctionLiveScreen` (rilanci). Il pull-to-refresh remonta la schermata
 * attiva incrementando `refreshKey`.
 *
 * Il parametro `modalita` (es. da una notifica dell'asta a rilanci, vedi
 * notificationDestination.ts) sceglie la scheda all'apertura e la cambia
 * quando arriva una nuova navigazione con parametri diversi.
 */
export function AuctionHubScreen() {
  const navigation = useNavigation<NavigationProp<AppTabParamList>>();
  const { activeLeagueId } = useAuthSession();
  const route = useRoute<RouteProp<AppTabParamList, "Auction">>();
  const requested = auctionModeFromParams(route.params);
  const [mode, setMode] = useState<AuctionMode>(requested ?? "buste");

  // Dipende dall'oggetto `route.params`, non solo dal valore: una seconda notifica
  // «live» dopo che l'utente è passato a mano alle buste riporta comunque su «Live».
  useEffect(() => {
    const next = auctionModeFromParams(route.params);
    if (next) {
      setMode(next);
    }
  }, [route.params]);
  const [refreshKey, setRefreshKey] = useState(0);
  const [refreshing, setRefreshing] = useState(false);

  function onRefresh() {
    setRefreshing(true);
    setRefreshKey((key) => key + 1);
    setRefreshing(false);
  }

  return (
    <PageContainer title="Asta" testID="screen-auction" refreshing={refreshing} onRefresh={onRefresh}>
      <ScreenTabs
        items={MARKET_HUB_TABS}
        activeId="Auction"
        onSelect={(id) => navigation.navigate(id as keyof AppTabParamList)}
        testID="market-hub-tabs"
      />
      {auctionHubHasLeague(activeLeagueId) ? (
        <>
          <MarketGateBar />
          <ScreenTabs
            items={AUCTION_MODE_TABS}
            activeId={mode}
            onSelect={(id) => setMode(id as AuctionMode)}
            testID="auction-mode-tabs"
          />
          {mode === "buste" ? <AuctionScreen key={refreshKey} /> : <AuctionLiveScreen key={refreshKey} />}
        </>
      ) : (
        // Account senza leghe: niente «Mercato aperto» né «Configura asta» (corsa M4, 22/11).
        <UiStatePanel
          state="empty"
          title="Nessuna lega"
          message="L'asta si svolge dentro una lega: creane una o unisciti con un codice invito."
          testID="auction-no-league"
        />
      )}
    </PageContainer>
  );
}
