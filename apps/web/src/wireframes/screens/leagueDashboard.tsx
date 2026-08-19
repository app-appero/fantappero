import {
  Breadcrumb,
  Button,
  Card,
  CardBody,
  CardHeader,
  PageContainer,
  WireframeSection,
} from "@fantappero/ui";
import { useAuth } from "../../auth/AuthContext";
import { WireframePage } from "../WireframePage";

export function LeagueDashboardWireframe() {
  const { leagues, activeLeague } = useAuth();

  return (
    <PageContainer
      title="Le tue leghe"
      header={<Breadcrumb items={[{ label: "Leghe" }]} />}
    >
      <WireframePage
        screenId="league-dashboard"
        successContent={
          <>
            <WireframeSection label="Elenco leghe" testId="wireframe-region-leagues">
              <ul className="fa-league-list">
                {leagues.map((league) => (
                  <li key={league.id} className="fa-league-list__item">
                    <Card>
                      <CardHeader>{league.name}</CardHeader>
                      <CardBody>
                        <p>
                          Ruolo:{" "}
                          {league.role === "league_admin" ? "Amministratore" : "Partecipante"}
                        </p>
                        <p>Stato: Attiva</p>
                        <Button variant="primary">Entra in lega</Button>
                      </CardBody>
                    </Card>
                  </li>
                ))}
              </ul>
            </WireframeSection>
            <WireframeSection label="Lega attiva" testId="wireframe-region-active-league">
              <p>
                Contesto corrente: <strong>{activeLeague?.name ?? "—"}</strong>
              </p>
            </WireframeSection>
            <WireframeSection label="Azioni rapide" testId="wireframe-region-quick-actions">
              <div className="fa-ds-showcase__row">
                <Button variant="secondary">Crea lega</Button>
                <Button variant="ghost">Unisciti con codice</Button>
              </div>
            </WireframeSection>
          </>
        }
      />
    </PageContainer>
  );
}
