import { Tab, TabList, TabPanel, Tabs } from "@fantappero/ui";
import { useAuth } from "../auth/AuthContext";
import { RequirePermissions } from "../auth/RequirePermissions";
import { useLocation, useNavigate } from "../router/simpleRouter";
import { AuctionPage } from "./AuctionPage";
import { MarketPage } from "./MarketPage";
import { RosterPage } from "./RosterPage";
import { WaiverPage } from "./WaiverPage";

const TABS = [
  { value: "rosa", label: "Rosa", path: "/rosa", permission: "roster:view" as const },
  { value: "asta", label: "Asta", path: "/asta", permission: "market:view" as const },
  { value: "svincoli", label: "Svincolati", path: "/svincoli", permission: "market:view" as const },
  { value: "mercato", label: "Mercato", path: "/mercato", permission: "market:view" as const },
];

/** Rosa/Asta/Svincolati/Mercato riuniti in un'unica pagina: sono tutti movimento giocatori. */
export function MarketHubPage() {
  const { pathname } = useLocation();
  const navigate = useNavigate();
  const { can } = useAuth();
  const activeTab = TABS.find((tab) => tab.path === pathname)?.value ?? "mercato";

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
        {TABS.filter((tab) => can([tab.permission])).map((tab) => (
          <Tab key={tab.value} value={tab.value}>
            {tab.label}
          </Tab>
        ))}
      </TabList>
      <TabPanel value="rosa">
        <RequirePermissions required={["roster:view"]}>
          <RosterPage />
        </RequirePermissions>
      </TabPanel>
      <TabPanel value="asta">
        <RequirePermissions required={["market:view"]}>
          <AuctionPage />
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
