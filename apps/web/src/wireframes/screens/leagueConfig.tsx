import {
  Breadcrumb,
  Button,
  Input,
  PageContainer,
  Select,
  WireframeSection,
} from "@fantappero/ui";
import { WireframePage } from "../WireframePage";

export function LeagueConfigWireframe() {
  return (
    <PageContainer
      title="Amministrazione lega"
      header={
        <Breadcrumb
          items={[
            { label: "Leghe", href: "/leghe" },
            { label: "Amministrazione" },
          ]}
        />
      }
    >
      <WireframePage
        screenId="league-config"
        successContent={
          <>
            <WireframeSection label="Regole lega" testId="wireframe-region-rules">
              <Select
                label="Preset regole"
                name="preset"
                value="standard"
                onChange={() => undefined}
                options={[{ value: "standard", label: "Standard (35 giocatori, 1000 crediti)" }]}
              />
              <Input label="Nome lega" name="league-name" defaultValue="Lega Demo" />
            </WireframeSection>
            <WireframeSection label="Partecipanti" testId="wireframe-region-members">
              <ul className="fa-wireframe-list">
                <li>Marco — Amministratore</li>
                <li>Giulia — Partecipante</li>
                <li>Luca — Partecipante</li>
              </ul>
              <Button variant="secondary">Invita partecipante</Button>
            </WireframeSection>
            <WireframeSection label="Avvio stagione" testId="wireframe-region-season">
              <p>Stato lega: Configurazione</p>
              <Button variant="primary">Salva configurazione</Button>
            </WireframeSection>
          </>
        }
      />
    </PageContainer>
  );
}
