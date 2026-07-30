import {
  AnomalyIndicator,
  Breadcrumb,
  Button,
  PageContainer,
  WireframeSection,
} from "@fantappero/ui";
import { useAuth } from "../../auth/AuthContext";
import { WireframePage } from "../WireframePage";

export function MarketWireframe() {
  const { can } = useAuth();
  const isAdmin = can(["market:manage"]);

  return (
    <PageContainer
      title="Mercato"
      header={
        <Breadcrumb
          items={[
            { label: "Leghe", href: "/leghe" },
            { label: "Mercato" },
          ]}
        />
      }
    >
      <WireframePage
        screenId="market"
        successContent={
          <>
            <WireframeSection label="Svincolati" testId="wireframe-region-free-agents">
              <ul className="fa-wireframe-list">
                <li>M. Thuram (A) — 38 cr.</li>
                <li>P. Fagioli (C) — 12 cr.</li>
              </ul>
              <Button variant="primary">Proponi scambio</Button>
            </WireframeSection>
            {isAdmin ? (
              <WireframeSection label="Approvazioni admin" testId="wireframe-region-market-admin">
                <p>2 proposte in attesa di approvazione</p>
                <Button variant="secondary">Gestisci proposte</Button>
              </WireframeSection>
            ) : (
              <WireframeSection label="Le tue proposte" testId="wireframe-region-market-proposals">
                <p>Nessuna proposta inviata in questo turno.</p>
              </WireframeSection>
            )}
            <AnomalyIndicator
              severity="info"
              severityLabel="Info"
              message="Nessuna anomalia di mercato rilevata per questo turno."
            />
          </>
        }
      />
    </PageContainer>
  );
}
