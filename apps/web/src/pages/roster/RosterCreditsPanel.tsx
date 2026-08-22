import type { CreditAccount, CreditLedgerList, FantasyTeamSummary } from "@fantappero/contracts";
import { Button, UiStatePanel } from "@fantappero/ui";
import { formatLedgerEntry, LEDGER_PAGE_SIZE } from "./rosterHelpers";

export function RosterCreditsPanel({
  isAdmin,
  leagueTeams,
  adminTeamId,
  onSelectAdminTeam,
  adminBusy,
  adjusting,
  hasAdjustTarget,
  credits,
  adjustAmount,
  onAdjustAmountChange,
  adjustNote,
  onAdjustNoteChange,
  onAdminAdjust,
  adjustMessage,
  adjustError,
  hasLedger,
  pagedLedgerEntries,
  ledgerEntriesCount,
  safeLedgerPage,
  ledgerPageCount,
  onLedgerPagePrev,
  onLedgerPageNext,
}: {
  isAdmin: boolean;
  leagueTeams: FantasyTeamSummary[];
  adminTeamId: string;
  onSelectAdminTeam: (teamId: string) => void;
  adminBusy: boolean;
  adjusting: boolean;
  hasAdjustTarget: boolean;
  credits: CreditAccount | null;
  adjustAmount: string;
  onAdjustAmountChange: (value: string) => void;
  adjustNote: string;
  onAdjustNoteChange: (value: string) => void;
  onAdminAdjust: () => void | Promise<void>;
  adjustMessage: string | null;
  adjustError: string | null;
  hasLedger: boolean;
  pagedLedgerEntries: CreditLedgerList["entries"];
  ledgerEntriesCount: number;
  safeLedgerPage: number;
  ledgerPageCount: number;
  onLedgerPagePrev: () => void;
  onLedgerPageNext: () => void;
}) {
  return (
    <div data-testid="roster-credits" style={{ marginBottom: "1rem" }}>
      {isAdmin && leagueTeams.length > 0 ? (
        <label
          style={{
            display: "flex",
            flexWrap: "wrap",
            alignItems: "center",
            gap: "0.5rem",
            marginBottom: "0.75rem",
          }}
        >
          <span style={{ fontWeight: 600 }}>Squadra target</span>
          <select
            data-testid="roster-admin-team"
            value={adminTeamId}
            onChange={(event) => onSelectAdminTeam(event.target.value)}
            disabled={adminBusy || adjusting}
            style={{ minWidth: "16rem", minHeight: "2.25rem" }}
          >
            {leagueTeams.map((row) => (
              <option key={row.id} value={row.id}>
                {row.name}
                {row.userType === "ai" ? " (IA)" : ""} ({row.filledSlots}/
                {row.rosterSize})
              </option>
            ))}
          </select>
        </label>
      ) : null}
      <div
        style={{
          display: "flex",
          flexWrap: "wrap",
          alignItems: "center",
          gap: "0.75rem 1rem",
          marginBottom: "0.5rem",
        }}
      >
        <p data-testid="roster-credits-balance" style={{ margin: 0 }}>
          Crediti residui: <strong>{credits?.balance ?? "—"}</strong>
          {credits ? ` (versione ${credits.version})` : null}
        </p>
        {isAdmin ? (
          <div
            data-testid="roster-admin-credits"
            style={{
              display: "flex",
              flexWrap: "wrap",
              alignItems: "center",
              gap: "0.5rem",
            }}
          >
            <label>
              Importo{" "}
              <input
                data-testid="roster-adjust-amount"
                value={adjustAmount}
                onChange={(event) => onAdjustAmountChange(event.target.value)}
              />
            </label>
            <label>
              Nota{" "}
              <input
                data-testid="roster-adjust-note"
                value={adjustNote}
                onChange={(event) => onAdjustNoteChange(event.target.value)}
              />
            </label>
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
      </div>
      {adjustMessage ? <p data-testid="roster-adjust-ok">{adjustMessage}</p> : null}
      {adjustError ? <p data-testid="roster-adjust-error">{adjustError}</p> : null}
      {hasLedger ? (
        <div data-testid="roster-credits-ledger">
          <ul>
            {pagedLedgerEntries.map((entry) => (
              <li key={entry.id}>{formatLedgerEntry(entry)}</li>
            ))}
          </ul>
          {ledgerEntriesCount > LEDGER_PAGE_SIZE ? (
            <div
              style={{
                display: "flex",
                flexWrap: "wrap",
                alignItems: "center",
                gap: "0.5rem",
                marginTop: "0.5rem",
              }}
            >
              <Button
                type="button"
                variant="secondary"
                disabled={safeLedgerPage <= 0}
                data-testid="roster-credits-ledger-prev"
                onClick={onLedgerPagePrev}
              >
                Precedenti
              </Button>
              <span data-testid="roster-credits-ledger-page">
                {safeLedgerPage + 1}/{ledgerPageCount}
              </span>
              <Button
                type="button"
                variant="secondary"
                disabled={safeLedgerPage >= ledgerPageCount - 1}
                data-testid="roster-credits-ledger-next"
                onClick={onLedgerPageNext}
              >
                Successivi
              </Button>
            </div>
          ) : null}
        </div>
      ) : (
        <UiStatePanel
          state="empty"
          title="Nessun movimento"
          message="Il ledger crediti non contiene ancora movimenti."
          testId="roster-credits-empty"
        />
      )}
    </div>
  );
}
