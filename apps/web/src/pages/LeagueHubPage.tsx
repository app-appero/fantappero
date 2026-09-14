import { Tab, TabList, TabPanel, Tabs } from "@fantappero/ui";
import { useEffect } from "react";
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
 *
 * Per evitare contenuti duplicati (EP13-P02), i due tab non sono più mostrati
 * entrambi allo stesso utente: chi ha `league:admin` vede solo Amministrazione
 * (che include già stato lega, regolamento e partecipanti), gli altri membri
 * vedono solo Home lega. Un admin che atterra su /lega/home (link vecchi,
 * preferiti…) viene reindirizzato in automatico su Amministrazione.
 */
export function LeagueHubPage() {
  const { pathname } = useLocation();
  const navigate = useNavigate();
  const { can } = useAuth();
  const isAdmin = can(["league:admin"]);
  const visibleTabs = isAdmin
    ? TABS.filter((tab) => tab.value === "league-admin")
    : TABS.filter((tab) => tab.value === "league-home" && can([tab.permission]));

  const requestedTab = TABS.find((tab) => tab.path === pathname)?.value ?? "league-home";
  const activeTab = isAdmin && requestedTab === "league-home" ? "league-admin" : requestedTab;

  useEffect(() => {
    const target = TABS.find((tab) => tab.value === activeTab);
    if (target && target.path !== pathname) {
      navigate(target.path, { replace: true });
    }
  }, [activeTab, pathname, navigate]);

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
