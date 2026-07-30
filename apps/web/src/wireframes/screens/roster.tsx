import {
  Breadcrumb,
  Button,
  PageContainer,
  PlayerCard,
  WireframeSection,
} from "@fantappero/ui";
import { useAuth } from "../../auth/AuthContext";
import { WireframePage } from "../WireframePage";

export function RosterWireframe() {
  const { can } = useAuth();
  const isAdmin = can(["market:manage"]);

  return (
    <PageContainer
      title="Rosa"
      density="compact"
      header={
        <Breadcrumb
          items={[
            { label: "Leghe", href: "/leghe" },
            { label: "Rosa" },
          ]}
        />
      }
    >
      <WireframePage
        screenId="roster"
        successContent={
          <>
            <WireframeSection label="Crediti e vincoli" testId="wireframe-region-credits">
              <p>Crediti residui: <strong>120</strong> · Giocatori: <strong>28/35</strong></p>
            </WireframeSection>
            <WireframeSection label="Listone rosa" testId="wireframe-region-roster-list">
              <PlayerCard
                name="L. Martinez"
                role="A"
                club="Inter"
                rating={7.5}
                statusLabel="Titolare probabile"
                statusVariant="success"
              />
              <PlayerCard
                name="N. Barella"
                role="C"
                club="Inter"
                rating={6.8}
                statusLabel="Infortunato"
                statusVariant="warning"
              />
            </WireframeSection>
            {isAdmin ? (
              <WireframeSection label="Strumenti admin" testId="wireframe-region-admin-tools">
                <Button variant="secondary">Importa CSV</Button>
                <Button variant="ghost">Cronologia modifiche</Button>
              </WireframeSection>
            ) : null}
          </>
        }
      />
    </PageContainer>
  );
}
