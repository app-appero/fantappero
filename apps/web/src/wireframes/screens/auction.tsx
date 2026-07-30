import {
  AuctionBidPanel,
  Breadcrumb,
  Button,
  PageContainer,
  WireframeSection,
} from "@fantappero/ui";
import { useAuth } from "../../auth/AuthContext";
import { WireframePage } from "../WireframePage";

export function AuctionWireframe() {
  const { can } = useAuth();
  const isAdmin = can(["market:manage"]);

  return (
    <PageContainer
      title="Asta"
      header={
        <Breadcrumb
          items={[
            { label: "Leghe", href: "/leghe" },
            { label: "Asta" },
          ]}
        />
      }
    >
      <WireframePage
        screenId="auction"
        successContent={
          <>
            {isAdmin ? (
              <WireframeSection label="Gestione sessione (admin)" testId="wireframe-region-auction-admin">
                <div className="fa-ds-showcase__row">
                  <Button variant="primary">Apri asta</Button>
                  <Button variant="secondary">Chiudi asta</Button>
                </div>
                <p>Sessione: Aperta · Partecipanti: 6/8</p>
              </WireframeSection>
            ) : null}
            <WireframeSection label="Offerta busta chiusa" testId="wireframe-region-auction-bid">
              <AuctionBidPanel
                title="Nuova offerta"
                budgetLabel="Budget residuo"
                budgetValue="420 crediti"
                playerLabel="Giocatore"
                playerPlaceholder="Cerca giocatore…"
                bidLabel="Offerta (crediti)"
                bidPlaceholder="Es. 45"
                submitLabel="Invia offerta"
                statusLabel="Stato"
                statusMessage="Asta a buste chiuse — offerta visibile solo a te fino alla chiusura."
              />
            </WireframeSection>
          </>
        }
      />
    </PageContainer>
  );
}
