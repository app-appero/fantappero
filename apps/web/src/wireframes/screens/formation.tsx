import {
  Breadcrumb,
  Button,
  FormationView,
  PageContainer,
  WireframeSection,
} from "@fantappero/ui";
import { WireframePage } from "../WireframePage";

export function FormationWireframe() {
  return (
    <PageContainer
      title="Formazione"
      header={
        <Breadcrumb
          items={[
            { label: "Leghe", href: "/leghe" },
            { label: "Formazione" },
          ]}
        />
      }
    >
      <WireframePage
        screenId="formation"
        successContent={
          <>
            <WireframeSection label="Modulo e lock" testId="wireframe-region-module">
              <p>Lock progressivo attivo — slot si chiudono al kickoff.</p>
            </WireframeSection>
            <WireframeSection label="Campo formazione" testId="wireframe-region-pitch">
              <FormationView
                title="Modulo 4-3-3"
                pitchAriaLabel="Formazione titolare"
                benchAriaLabel="Panchina"
                benchTitle="Panchina"
                slots={[
                  { id: "p1", label: "Portiere", role: "P", playerName: "Maignan" },
                  { id: "d1", label: "Difensore", role: "D", playerName: "Bastoni" },
                  { id: "c1", label: "Centrocampista", role: "C", playerName: "Barella" },
                  { id: "a1", label: "Attaccante", role: "A", playerName: "Martinez" },
                ]}
                bench={[{ id: "b1", label: "Riserva", role: "P", playerName: "Meret" }]}
              />
            </WireframeSection>
            <WireframeSection label="Mosse tattiche" testId="wireframe-region-tactics">
              <p>Mosse disponibili: 2/3</p>
              <Button variant="primary">Salva formazione</Button>
            </WireframeSection>
          </>
        }
      />
    </PageContainer>
  );
}
