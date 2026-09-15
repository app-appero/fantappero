import { Breadcrumb, PageContainer, Tab, TabList, TabPanel, Tabs } from "@fantappero/ui";
import { useLocation, useNavigate } from "../router/simpleRouter";
import { AuctionLivePage } from "./AuctionLivePage";
import { AuctionPage } from "./AuctionPage";

/** Asta: buste chiuse e live come sotto-schede della stessa sezione (EP08-01/02/09). */
export function AuctionHubPage() {
  const { pathname, search } = useLocation();
  const navigate = useNavigate();
  const activeSubTab = pathname === "/asta-live" ? "live" : "buste";
  const persona = new URLSearchParams(search).get("persona");
  const withPersona = (path: string) =>
    persona ? `${path}?persona=${encodeURIComponent(persona)}` : path;

  return (
    <PageContainer
      title="Asta"
      density="compact"
      header={<Breadcrumb items={[{ label: "Leghe", href: "/leghe" }, { label: "Asta" }]} />}
    >
      <Tabs
        value={activeSubTab}
        onValueChange={(value) => navigate(withPersona(value === "live" ? "/asta-live" : "/asta"))}
        aria-label="Modalità asta"
      >
        <TabList>
          <Tab value="buste">Buste chiuse</Tab>
          <Tab value="live">Live</Tab>
        </TabList>
        <TabPanel value="buste">
          <AuctionPage />
        </TabPanel>
        <TabPanel value="live">
          <AuctionLivePage />
        </TabPanel>
      </Tabs>
    </PageContainer>
  );
}
