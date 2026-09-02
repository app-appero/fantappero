import {
  AnomalyIndicator,
  EmptyState,
  PageContainer,
  UiStatePanel,
  WireframeSection,
} from "@fantappero/ui";
import { WireframePage } from "../WireframePage";

export function OperatorDashboardWireframe() {
  return (
    <PageContainer title="Pannello operatore globale">
      <WireframePage
        screenId="operator-panel"
        successContent={
          <>
            <WireframeSection label="Monitoraggio piattaforma" testId="wireframe-region-operator-dashboard">
              <UiStatePanel
                state="success"
                title="Operazioni piattaforma"
                message="Area distinta dall'app lega — monitoraggio e interventi globali."
              />
            </WireframeSection>
            <WireframeSection label="Anomalie dati" testId="wireframe-region-anomalies">
              <AnomalyIndicator
                severity="warning"
                severityLabel="Attenzione"
                message="2 leghe con risultati provvisori in attesa di revisione."
                detail="Revisione manuale richiesta prima della pubblicazione definitiva."
              />
            </WireframeSection>
          </>
        }
      />
    </PageContainer>
  );
}

export function OperatorLeaguesWireframe() {
  return (
    <PageContainer title="Leghe globali">
      <WireframePage
        screenId="operator-panel"
        successContent={
          <WireframeSection label="Elenco leghe piattaforma" testId="wireframe-region-operator-leagues">
            <EmptyState
              title="Elenco leghe"
              description="Vista operatore — dati reali da API amministrative (EP11-04)."
              testId="admin-leagues-empty"
            />
          </WireframeSection>
        }
      />
    </PageContainer>
  );
}

export function OperatorUsersWireframe() {
  return (
    <PageContainer title="Utenti">
      <WireframePage
        screenId="operator-panel"
        successContent={
          <WireframeSection label="Utenti piattaforma" testId="wireframe-region-operator-users">
            <ul className="fa-wireframe-list">
              <li>marco@esempio.it — Membro</li>
              <li>giulia@esempio.it — Membro</li>
              <li>admin@esempio.it — Operatore globale</li>
            </ul>
          </WireframeSection>
        }
      />
    </PageContainer>
  );
}
