import { Tab, TabList, TabPanel, Tabs } from "@fantappero/ui";
import { useAuth } from "../auth/AuthContext";
import { RequirePermissions } from "../auth/RequirePermissions";
import { useLocation, useNavigate } from "../router/simpleRouter";
import { LeagueAdminPage } from "./LeagueAdminPage";
import { LeagueHomePage } from "./LeagueHomePage";

const TABS = [
  { value: "league-home", label: "Home lega", path: "/lega/home", permission: "league:view" as const },
  {
    value: "league-admin",
    label: "Amministrazione lega",
    path: "/lega/amministrazione",
    permission: "league:admin" as const,
  },
];

/**
 * Home lega/Amministrazione riunite in un'unica pagina a tab (EP13-P01).
 * Scegliere/creare/unirsi a una lega è ora nell'header, sempre visibile.
 */
export function LeagueHubPage() {
  const { pathname } = useLocation();
  const navigate = useNavigate();
  const { can } = useAuth();
  const activeTab = TABS.find((tab) => tab.path === pathname)?.value ?? "league-home";
  const visibleTabs = TABS.filter((tab) => can([tab.permission]));

  return (
    <Tabs
      value={activeTab}
      onValueChange={(value) => {
        const target = TABS.find((tab) => tab.value === value);
        if (target) navigate(target.path);
      }}
      aria-label="Lega"
    >
      {visibleTabs.length > 1 ? (
        <TabList>
          {visibleTabs.map((tab) => (
            <Tab key={tab.value} value={tab.value}>
              {tab.label}
            </Tab>
          ))}
        </TabList>
      ) : null}
      <TabPanel value="league-home">
        <RequirePermissions required={["league:view"]}>
          <LeagueHomePage />
        </RequirePermissions>
      </TabPanel>
      <TabPanel value="league-admin">
        <RequirePermissions required={["league:admin"]}>
          <LeagueAdminPage />
        </RequirePermissions>
      </TabPanel>
    </Tabs>
  );
}
