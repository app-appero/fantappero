import type { FantasyRole, FantasyTeam } from "@fantappero/contracts";
import { Badge, Table, TableBody, TableCell, TableHead, TableHeaderCell, TableRow, Button } from "@fantappero/ui";
import {
  compositionStatusLabel,
  compositionStatusVariant,
  ROLE_SECTION_ORDER,
  ROLE_SECTION_TITLE,
  roleBadgeVariant,
} from "./rosterHelpers";

type RosterSlot = FantasyTeam["slots"][number];

export function RosterFilledSummary({
  viewedTeam,
  filledByRole,
  canEdit,
  adminBusy,
  onReleaseAthlete,
}: {
  viewedTeam: FantasyTeam;
  filledByRole: Record<FantasyRole | "unknown", RosterSlot[]>;
  canEdit: boolean;
  adminBusy: boolean;
  onReleaseAthlete: (athleteId: string) => void | Promise<void>;
}) {
  const compositionLimits = viewedTeam.composition?.limits;
  const roleLimit = (role: FantasyRole): number | null => {
    if (!compositionLimits) {
      return null;
    }
    if (role === "P") {
      return compositionLimits.goalkeepers;
    }
    if (role === "D") {
      return compositionLimits.defenders;
    }
    if (role === "C") {
      return compositionLimits.midfielders;
    }
    return compositionLimits.forwards;
  };

  return (
    <div data-testid="wireframe-roster-success">
      <p data-testid="roster-summary">
        {viewedTeam.name}: {viewedTeam.filledSlots}/{viewedTeam.rosterSize} giocatori
      </p>
      {viewedTeam.composition ? (
        <div data-testid="roster-composition">
          <p>
            Composizione:{" "}
            <Badge variant={compositionStatusVariant(viewedTeam.composition.status)}>
              <span data-testid="roster-composition-status">
                {compositionStatusLabel(viewedTeam.composition.status)}
              </span>
            </Badge>
          </p>
          <p data-testid="roster-composition-counts">
            {viewedTeam.composition.counts.P}/{viewedTeam.composition.limits.goalkeepers}P ·{" "}
            {viewedTeam.composition.counts.D}/{viewedTeam.composition.limits.defenders}D ·{" "}
            {viewedTeam.composition.counts.C}/{viewedTeam.composition.limits.midfielders}C ·{" "}
            {viewedTeam.composition.counts.A}/{viewedTeam.composition.limits.forwards}A ·{" "}
            {viewedTeam.composition.competitionCount} campionati
          </p>
          {viewedTeam.composition.issues.length > 0 ? (
            <ul data-testid="roster-composition-issues">
              {viewedTeam.composition.issues.map((issue) => (
                <li key={`${issue.code}-${issue.message}`}>{issue.message}</li>
              ))}
            </ul>
          ) : null}
        </div>
      ) : null}
      <div className="fa-roster-role-tables" data-testid="roster-filled-table">
        {ROLE_SECTION_ORDER.map((role) => {
          const slots = filledByRole[role];
          const limit = roleLimit(role);
          return (
            <section key={role} className="fa-roster-role-section" data-testid={`roster-filled-table-${role}`}>
              <h3 className="fa-roster-role-section__title">
                <Badge variant={roleBadgeVariant(role)}>{role}</Badge>{" "}
                {ROLE_SECTION_TITLE[role]}
                <span className="fa-roster-role-section__count">
                  {slots.length}
                  {limit != null ? `/${limit}` : ""}
                </span>
              </h3>
              {slots.length === 0 ? (
                <p className="fa-roster-role-section__empty">Nessun giocatore in questo ruolo.</p>
              ) : (
                <Table compact>
                  <TableHead>
                    <TableRow>
                      <TableHeaderCell>Calciatore</TableHeaderCell>
                      <TableHeaderCell>Club</TableHeaderCell>
                      <TableHeaderCell>Crediti acquisto</TableHeaderCell>
                      <TableHeaderCell>Slot</TableHeaderCell>
                      {canEdit ? <TableHeaderCell>Azione</TableHeaderCell> : null}
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {slots.map((slot) => (
                      <TableRow key={slot.id}>
                        <TableCell>{slot.athleteName ?? "Calciatore"}</TableCell>
                        <TableCell>{slot.clubName ?? "—"}</TableCell>
                        <TableCell>{slot.purchaseCredits ?? "—"}</TableCell>
                        <TableCell>{slot.slotIndex + 1}</TableCell>
                        {canEdit ? (
                          <TableCell>
                            {slot.athleteId ? (
                              <Button
                                type="button"
                                variant="secondary"
                                disabled={adminBusy}
                                data-testid={`roster-admin-release-${slot.athleteId}`}
                                onClick={() => void onReleaseAthlete(slot.athleteId!)}
                              >
                                Rimuovi
                              </Button>
                            ) : null}
                          </TableCell>
                        ) : null}
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </section>
          );
        })}
        {filledByRole.unknown.length > 0 ? (
          <section className="fa-roster-role-section" data-testid="roster-filled-table-unknown">
            <h3 className="fa-roster-role-section__title">
              Senza ruolo
              <span className="fa-roster-role-section__count">{filledByRole.unknown.length}</span>
            </h3>
            <Table compact>
              <TableHead>
                <TableRow>
                  <TableHeaderCell>Calciatore</TableHeaderCell>
                  <TableHeaderCell>Club</TableHeaderCell>
                  <TableHeaderCell>Crediti acquisto</TableHeaderCell>
                  <TableHeaderCell>Slot</TableHeaderCell>
                  {canEdit ? <TableHeaderCell>Azione</TableHeaderCell> : null}
                </TableRow>
              </TableHead>
              <TableBody>
                {filledByRole.unknown.map((slot) => (
                  <TableRow key={slot.id}>
                    <TableCell>{slot.athleteName ?? "Calciatore"}</TableCell>
                    <TableCell>{slot.clubName ?? "—"}</TableCell>
                    <TableCell>{slot.purchaseCredits ?? "—"}</TableCell>
                    <TableCell>{slot.slotIndex + 1}</TableCell>
                    {canEdit ? (
                      <TableCell>
                        {slot.athleteId ? (
                          <Button
                            type="button"
                            variant="secondary"
                            disabled={adminBusy}
                            data-testid={`roster-admin-release-${slot.athleteId}`}
                            onClick={() => void onReleaseAthlete(slot.athleteId!)}
                          >
                            Rimuovi
                          </Button>
                        ) : null}
                      </TableCell>
                    ) : null}
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </section>
        ) : null}
      </div>
    </div>
  );
}
