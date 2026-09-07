import type { FantasyTeamSummary, CreditAccount } from "@fantappero/contracts";
import { Button, Card, CardBody, Input, Select } from "@fantappero/ui";

export function RosterCreditsPanel({
  isAdmin,
  leagueTeams,
  adminTeamId,
  onSelectAdminTeam,
  credits,
  adminBusy,
  adjusting,
  hasAdjustTarget,
  adjustAmount,
  onAdjustAmountChange,
  adjustNote,
  onAdjustNoteChange,
  onAdminAdjust,
  adjustMessage,
  adjustError,
}: {
  isAdmin: boolean;
  leagueTeams: FantasyTeamSummary[];
  adminTeamId: string;
  onSelectAdminTeam: (teamId: string) => void;
  credits: CreditAccount | null;
  adminBusy: boolean;
  adjusting: boolean;
  hasAdjustTarget: boolean;
  adjustAmount: string;
  onAdjustAmountChange: (value: string) => void;
  adjustNote: string;
  onAdjustNoteChange: (value: string) => void;
  onAdminAdjust: () => void | Promise<void>;
  adjustMessage: string | null;
  adjustError: string | null;
}) {
  return (
    <Card data-testid="roster-credits" className="fa-roster-adjust-card">
      <CardBody>
        <div className="fa-roster-target-header__row">
          {isAdmin && leagueTeams.length > 0 ? (
            <Select
              label="Squadra"
              name="roster-admin-team"
              data-testid="roster-admin-team"
              value={adminTeamId}
              onChange={(event) => onSelectAdminTeam(event.target.value)}
              disabled={adminBusy || adjusting}
              options={leagueTeams.map((row) => ({
                value: row.id,
                label: `${row.name}${row.userType === "ai" ? " (IA)" : ""} (${row.filledSlots}/${row.rosterSize})`,
              }))}
            />
          ) : null}
          <p data-testid="roster-credits-balance" className="fa-roster-target-header__credits">
            Crediti residui: <strong>{credits?.balance ?? "—"}</strong>
          </p>
        </div>
        {isAdmin ? (
          <div className="fa-roster-adjust-card__row" data-testid="roster-admin-credits">
            <Input
              label="Importo"
              type="number"
              data-testid="roster-adjust-amount"
              value={adjustAmount}
              onChange={(event) => onAdjustAmountChange(event.target.value)}
            />
            <Input
              label="Nota"
              data-testid="roster-adjust-note"
              value={adjustNote}
              onChange={(event) => onAdjustNoteChange(event.target.value)}
            />
            <Button
              type="button"
              variant="secondary"
              disabled={adjusting || !hasAdjustTarget}
              onClick={() => void onAdminAdjust()}
            >
              {adjusting ? "Registrazione…" : "Aggiusta crediti"}
            </Button>
          </div>
        ) : null}
        {isAdmin && adjustMessage ? <p data-testid="roster-adjust-ok">{adjustMessage}</p> : null}
        {isAdmin && adjustError ? <p data-testid="roster-adjust-error">{adjustError}</p> : null}
      </CardBody>
    </Card>
  );
}
