import { Tab, TabList, TabPanel, Tabs } from "@fantappero/ui";
import { useAuth } from "../auth/AuthContext";
import { RequirePermissions } from "../auth/RequirePermissions";
import { useLocation, useNavigate } from "../router/simpleRouter";
import { AuctionHubPage } from "./AuctionHubPage";
import { MarketPage } from "./MarketPage";
import { RosterPage } from "./RosterPage";
import { WaiverPage } from "./WaiverPage";

// Mercato svincolati (sessione a buste chiuse) nascosta dalla tab bar: ADR-0006.
// Route, TabPanel e backend restano intatti e raggiungibili via URL diretto
// (/svincoli) — riattivare riportando questo flag a true.
const SHOW_WAIVER_TAB = false;

const TABS = [
  { value: "rosa", label: "Rosa", path: "/rosa", matchPaths: ["/rosa"], permission: "roster:view" as const },
  {
    value: "asta",
    label: "Asta",
    path: "/asta",
    matchPaths: ["/asta", "/asta-live"],
    permission: "market:view" as const,
  },
  { value: "svincoli", label: "Svincolati", path: "/svincoli", matchPaths: ["/svincoli"], permission: "market:view" as const },
  { value: "mercato", label: "Scambi", path: "/mercato", matchPaths: ["/mercato"], permission: "market:view" as const },
];

/**
 * Rosa/Asta/Svincolati/Scambi riuniti in un'unica pagina: sono tutti movimento giocatori.
 * La tab "svincoli" è nascosta (`SHOW_WAIVER_TAB`) e la tab "mercato" (route invariata
 * `/mercato`) mostra solo `MarketPage`, ora limitata alla proposta/gestione scambi — ADR-0006.
 */
export function MarketHubPage() {
  const { pathname } = useLocation();
  const navigate = useNavigate();
  const { can } = useAuth();
  const activeTab = TABS.find((tab) => tab.matchPaths.includes(pathname))?.value ?? "mercato";

  return (
    <Tabs
      value={activeTab}
      onValueChange={(value) => {
        const target = TABS.find((tab) => tab.value === value);
        if (target) navigate(target.path);
      }}
      aria-label="Mercato"
    >
      <TabList>
        {TABS.filter((tab) => can([tab.permission]) && (tab.value !== "svincoli" || SHOW_WAIVER_TAB)).map(
          (tab) => (
            <Tab key={tab.value} value={tab.value}>
              {tab.label}
            </Tab>
          ),
        )}
      </TabList>
      <TabPanel value="rosa">
        <RequirePermissions required={["roster:view"]}>
          <RosterPage />
        </RequirePermissions>
      </TabPanel>
      <TabPanel value="asta">
        <RequirePermissions required={["market:view"]}>
          <AuctionHubPage />
        </RequirePermissions>
      </TabPanel>
      <TabPanel value="svincoli">
        <RequirePermissions required={["market:view"]}>
          <WaiverPage />
        </RequirePermissions>
      </TabPanel>
      <TabPanel value="mercato">
        <RequirePermissions required={["market:view"]}>
          <MarketPage />
        </RequirePermissions>
      </TabPanel>
    </Tabs>
  );
}
