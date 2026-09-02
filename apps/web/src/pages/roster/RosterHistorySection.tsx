import type {
  RosterOwnershipHistory,
  RosterTurnSnapshotDetail,
  RosterTurnSnapshotSummary,
} from "@fantappero/contracts";
import {
  Button,
  Card,
  CardBody,
  CardHeader,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeaderCell,
  TableRow,
  UiStatePanel,
} from "@fantappero/ui";
import { roleLabel } from "./rosterHelpers";

export function RosterHistorySection({
  historyLoading,
  historyError,
  history,
  snapshots,
  snapshotDetail,
  snapshotRound,
  snapshotBusy,
  snapshotMessage,
  snapshotError,
  isAdmin,
  onSnapshotRoundChange,
  onSelectSnapshotRound,
  onCreateSnapshot,
}: {
  historyLoading: boolean;
  historyError: string | null;
  history: RosterOwnershipHistory | null;
  snapshots: RosterTurnSnapshotSummary[];
  snapshotDetail: RosterTurnSnapshotDetail | null;
  snapshotRound: string;
  snapshotBusy: boolean;
  snapshotMessage: string | null;
  snapshotError: string | null;
  isAdmin: boolean;
  onSnapshotRoundChange: (value: string) => void;
  onSelectSnapshotRound: (value: string) => void | Promise<void>;
  onCreateSnapshot: () => void | Promise<void>;
}) {
  return (
    <div data-testid="roster-history">
      {historyLoading ? (
        <UiStatePanel
          state="loading"
          title="Caricamento storico"
          message="Recupero intervalli di possesso e snapshot…"
          testId="roster-history-loading"
        />
      ) : null}
      {!historyLoading && historyError ? (
        <UiStatePanel
          state="error"
          title="Storico non disponibile"
          message={historyError}
          testId="roster-history-error"
        />
      ) : null}
      {!historyLoading && !historyError && history && history.intervals.length === 0 ? (
        <UiStatePanel
          state="empty"
          title="Nessun possesso registrato"
          message="Gli intervalli compaiono dopo assegnazioni o rilasci in rosa."
          testId="roster-history-empty"
        />
      ) : null}
      {!historyLoading && !historyError && history && history.intervals.length > 0 ? (
        <Card data-testid="roster-history-success">
          <CardHeader title="Intervalli di possesso" />
          <CardBody>
            <Table compact>
              <TableHead>
                <TableRow>
                  <TableHeaderCell>Calciatore</TableHeaderCell>
                  <TableHeaderCell>Slot</TableHeaderCell>
                  <TableHeaderCell>Crediti</TableHeaderCell>
                  <TableHeaderCell>Dal</TableHeaderCell>
                  <TableHeaderCell>Al</TableHeaderCell>
                  <TableHeaderCell>Fonte</TableHeaderCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {history.intervals.map((row) => (
                  <TableRow key={row.id}>
                    <TableCell>{row.athleteName ?? row.athleteId}</TableCell>
                    <TableCell>{row.slotIndex + 1}</TableCell>
                    <TableCell>{row.purchaseCredits}</TableCell>
                    <TableCell>{new Date(row.acquiredAt).toLocaleString("it-IT")}</TableCell>
                    <TableCell>
                      {row.releasedAt
                        ? new Date(row.releasedAt).toLocaleString("it-IT")
                        : "In rosa"}
                    </TableCell>
                    <TableCell>{row.source}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardBody>
        </Card>
      ) : null}

      <Card style={{ marginTop: "1rem" }} data-testid="roster-snapshots">
        <CardHeader title="Snapshot per turno" />
        <CardBody>
          <div
            style={{
              display: "flex",
              flexWrap: "wrap",
              gap: "0.5rem",
              alignItems: "center",
              marginBottom: "0.75rem",
            }}
          >
            <label>
              Turno{" "}
              <input
                data-testid="roster-snapshot-round"
                value={snapshotRound}
                onChange={(event) => onSnapshotRoundChange(event.target.value)}
                style={{ width: "4rem" }}
              />
            </label>
            {snapshots.length > 0 ? (
              <select
                data-testid="roster-snapshot-select"
                value={snapshotRound}
                onChange={(event) => void onSelectSnapshotRound(event.target.value)}
              >
                {snapshots.map((row) => (
                  <option key={row.id} value={String(row.roundNumber)}>
                    Turno {row.roundNumber} ({row.entryCount} slot)
                  </option>
                ))}
              </select>
            ) : null}
            {isAdmin ? (
              <Button
                type="button"
                variant="secondary"
                disabled={snapshotBusy}
                data-testid="roster-snapshot-create"
                onClick={() => void onCreateSnapshot()}
              >
                {snapshotBusy ? "Salvataggio…" : "Crea snapshot turno"}
              </Button>
            ) : null}
            <Button
              type="button"
              variant="secondary"
              disabled={snapshotBusy || !snapshotRound}
              data-testid="roster-snapshot-load"
              onClick={() => void onSelectSnapshotRound(snapshotRound)}
            >
              Carica
            </Button>
          </div>
          {snapshotMessage ? <p data-testid="roster-snapshot-ok">{snapshotMessage}</p> : null}
          {snapshotError ? <p data-testid="roster-snapshot-error">{snapshotError}</p> : null}
          {!snapshotDetail ? (
            <UiStatePanel
              state="empty"
              title="Nessuno snapshot"
              message="Crea uno snapshot per congelare la rosa di un turno."
              testId="roster-snapshot-empty"
            />
          ) : (
            <div data-testid="roster-snapshot-detail">
              <p>
                Turno {snapshotDetail.roundNumber} · catturato{" "}
                {new Date(snapshotDetail.capturedAt).toLocaleString("it-IT")} ·{" "}
                {snapshotDetail.entryCount} assegnazioni
              </p>
              <Table compact>
                <TableHead>
                  <TableRow>
                    <TableHeaderCell>Squadra</TableHeaderCell>
                    <TableHeaderCell>Calciatore</TableHeaderCell>
                    <TableHeaderCell>Ruolo</TableHeaderCell>
                    <TableHeaderCell>Crediti</TableHeaderCell>
                    <TableHeaderCell>Slot</TableHeaderCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {snapshotDetail.entries.map((entry) => (
                    <TableRow key={`${entry.fantasyTeamId}-${entry.slotIndex}-${entry.athleteId}`}>
                      <TableCell>{entry.teamName}</TableCell>
                      <TableCell>{entry.athleteName ?? entry.athleteId}</TableCell>
                      <TableCell>{roleLabel(entry.role)}</TableCell>
                      <TableCell>{entry.purchaseCredits}</TableCell>
                      <TableCell>{entry.slotIndex + 1}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </CardBody>
      </Card>
    </div>
  );
}
