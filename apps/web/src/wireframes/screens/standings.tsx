import {
  Breadcrumb,
  PageContainer,
  StandingsTable,
  WireframeSection,
} from "@fantappero/ui";
import { WireframePage } from "../WireframePage";

const DEMO_STANDINGS = [
  {
    id: "1",
    position: 1,
    teamName: "Rivali FC",
    played: 11,
    points: 24,
    goalsFor: 820,
    goalsAgainst: 760,
  },
  {
    id: "2",
    position: 2,
    teamName: "La tua squadra",
    played: 11,
    points: 22,
    goalsFor: 798,
    goalsAgainst: 772,
    isCurrentUser: true,
    highlightLabel: "Tu",
  },
  {
    id: "3",
    position: 3,
    teamName: "Underdogs",
    played: 11,
    points: 19,
    goalsFor: 755,
    goalsAgainst: 780,
  },
];

export function StandingsWireframe() {
  return (
    <PageContainer
      title="Classifica"
      density="compact"
      header={
        <Breadcrumb
          items={[
            { label: "Leghe", href: "/leghe" },
            { label: "Classifica" },
          ]}
        />
      }
    >
      <WireframePage
        screenId="standings"
        successContent={
          <WireframeSection label="Ranking lega" testId="wireframe-region-standings">
            <StandingsTable
              caption="Classifica lega"
              positionLabel="Pos."
              teamLabel="Squadra"
              playedLabel="G"
              pointsLabel="Pt"
              goalsLabel="GF:GS"
              rows={DEMO_STANDINGS}
            />
          </WireframeSection>
        }
      />
    </PageContainer>
  );
}
