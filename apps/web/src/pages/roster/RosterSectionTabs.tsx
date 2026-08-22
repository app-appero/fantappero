import { Button } from "@fantappero/ui";
import type { RosterPageSection } from "./rosterHelpers";

export function RosterSectionTabs({
  pageSection,
  onSelect,
}: {
  pageSection: RosterPageSection;
  onSelect: (section: RosterPageSection) => void;
}) {
  return (
    <div
      style={{ display: "flex", gap: "0.5rem", marginBottom: "1rem" }}
      data-testid="roster-section-tabs"
    >
      <Button
        type="button"
        variant={pageSection === "rosa" ? "primary" : "secondary"}
        data-testid="roster-section-rosa"
        onClick={() => onSelect("rosa")}
      >
        Rosa
      </Button>
      <Button
        type="button"
        variant={pageSection === "storico" ? "primary" : "secondary"}
        data-testid="roster-section-storico"
        onClick={() => onSelect("storico")}
      >
        Storico
      </Button>
    </div>
  );
}
