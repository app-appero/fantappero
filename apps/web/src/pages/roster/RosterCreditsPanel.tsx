import type { FantasyTeamSummary, CreditAccount } from "@fantappero/contracts";
import { Button, Input, Select } from "@fantappero/ui";
import { useState } from "react";

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
  const [open, setOpen] = useState(false);

  return (
    <div className="fa-roster-credits-bar" data-testid="roster-credits">
      {isAdmin && leagueTeams.length > 0 ? (
        <Select
          aria-label="Squadra"
          name="roster-admin-team"
          data-testid="roster-admin-team"
          value={adminTeamId}
          onChange={(event) => onSelectAdminTeam(event.target.value)}
          disabled={adminBusy || adjusting}
          options={leagueTeams.map((row) => ({
            value: row.id,
            label: `${row.name}${row.userType === "ai" ? " (IA)" : ""}`,
          }))}
        />
      ) : null}
      <p data-testid="roster-credits-balance" className="fa-roster-credits-bar__balance">
        Crediti residui: <strong>{credits?.balance ?? "—"}</strong>
      </p>
      {isAdmin ? (
        <div className="fa-roster-adjust" data-testid="roster-admin-credits">
          <Button
            type="button"
            variant="secondary"
            aria-expanded={open}
            onClick={() => setOpen((current) => !current)}
          >
            Aggiusta crediti
          </Button>
          {open ? (
            <div className="fa-roster-adjust__popover" role="dialog" aria-label="Aggiusta crediti">
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
                disabled={adjusting || !hasAdjustTarget}
                onClick={() => void onAdminAdjust()}
              >
                {adjusting ? "Registrazione…" : "Registra"}
              </Button>
              {adjustMessage ? <p data-testid="roster-adjust-ok">{adjustMessage}</p> : null}
              {adjustError ? <p data-testid="roster-adjust-error">{adjustError}</p> : null}
            </div>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
