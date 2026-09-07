import { useNavigation, type NavigationProp } from "@react-navigation/core";
import { useState } from "react";
import { ScreenTabs } from "../components/ScreenTabs";
import { PageContainer } from "../layout/PageContainer";
import { MARKET_HUB_TABS } from "../navigation/marketHubTabs";
import type { AppTabParamList } from "../navigation/types";
import { AuctionLiveScreen } from "./AuctionLiveScreen";
import { AuctionScreen } from "./AuctionScreen";

type AuctionMode = "buste" | "live";

const AUCTION_MODE_TABS = [
  { id: "buste", label: "Buste chiuse" },
  { id: "live", label: "Live" },
] as const;

/**
 * Asta: contenitore con la screen-tabs strip del market hub (Rosa/Asta/…) e,
 * al suo interno, il toggle "Buste chiuse"/"Live" tra `AuctionScreen` (sealed)
 * e `AuctionLiveScreen` (rilanci). Il pull-to-refresh remonta la schermata
 * attiva incrementando `refreshKey`.
 */
export function AuctionHubScreen() {
  const navigation = useNavigation<NavigationProp<AppTabParamList>>();
  const [mode, setMode] = useState<AuctionMode>("buste");
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
      <ScreenTabs
        items={AUCTION_MODE_TABS}
        activeId={mode}
        onSelect={(id) => setMode(id as AuctionMode)}
        testID="auction-mode-tabs"
      />
      {mode === "buste" ? <AuctionScreen key={refreshKey} /> : <AuctionLiveScreen key={refreshKey} />}
    </PageContainer>
  );
}
