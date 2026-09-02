import {
  Breadcrumb,
  KpiCard,
  MatchCard,
  PageContainer,
  ResultCard,
  Tab,
  TabList,
  TabPanel,
  Tabs,
  WireframeSection,
} from "@fantappero/ui";
import { useMemo, useState } from "react";
import { useLocation } from "../../router/simpleRouter";
import { WireframePage } from "../WireframePage";

export function MatchdayWireframe() {
  const { search } = useLocation();
  const initialTab = useMemo(() => {
    const params = new URLSearchParams(search.startsWith("?") ? search.slice(1) : search);
    return params.get("tab") === "risultati" ? "risultati" : "turno";
  }, [search]);
  const [tab, setTab] = useState(initialTab);

  return (
    <PageContainer
      title="Turni"
      header={
        <Breadcrumb
          items={[
            { label: "Leghe", href: "/leghe" },
            { label: "Turni" },
          ]}
        />
      }
    >
      <WireframePage
        screenId="matchday"
        successContent={
          <>
            <Tabs value={tab} onValueChange={setTab}>
              <TabList aria-label="Sezioni turno">
                <Tab value="turno">Turno</Tab>
                <Tab value="risultati">Risultati</Tab>
              </TabList>
              <TabPanel value="turno">
                <WireframeSection label="KPI turno" testId="wireframe-region-kpi">
                  <div className="fa-kpi-grid">
                    <KpiCard label="Punti turno" value={62} delta="+4 vs prec." trend="up" />
                    <KpiCard label="Posizione" value={2} delta="invariata" trend="neutral" />
                  </div>
                </WireframeSection>
                <WireframeSection label="Calendario" testId="wireframe-region-fixtures">
                  <MatchCard
                    homeTeam="La tua squadra"
                    awayTeam="Avversario"
                    kickoffLabel="Sab 18:30"
                    status="scheduled"
                    statusLabel="Programmata"
                    contextLabel="Turno 12"
                  />
                </WireframeSection>
              </TabPanel>
              <TabPanel value="risultati">
                <WireframeSection label="Esito fantasy" testId="wireframe-region-results">
                  <ResultCard
                    homeTeam="Tu"
                    awayTeam="Rivali FC"
                    homeScore={78}
                    awayScore={72}
                    caption="Esito turno 11 — provvisorio"
                    scoreAriaLabel="Risultato fantasy"
                  />
                </WireframeSection>
              </TabPanel>
            </Tabs>
          </>
        }
      />
    </PageContainer>
  );
}
