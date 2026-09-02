import type { RosterImportPreview } from "@fantappero/contracts";
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
import type { RefObject } from "react";

export function RosterCsvImportCard({
  csvBusy,
  onDownloadCsvTemplate,
  csvFileInputRef,
  onCsvFileSelected,
  csvCanConfirm,
  onConfirmCsvImport,
  csvMessage,
  csvError,
  csvPreview,
  csvResolutions,
  onCsvResolutionChange,
}: {
  csvBusy: boolean;
  onDownloadCsvTemplate: () => void | Promise<void>;
  csvFileInputRef: RefObject<HTMLInputElement | null>;
  onCsvFileSelected: (file: File | null) => void | Promise<void>;
  csvCanConfirm: boolean;
  onConfirmCsvImport: () => void | Promise<void>;
  csvMessage: string | null;
  csvError: string | null;
  csvPreview: RosterImportPreview | null;
  csvResolutions: Record<number, string>;
  onCsvResolutionChange: (rowNumber: number, athleteId: string) => void;
}) {
  return (
    <Card style={{ marginTop: "1rem" }} data-testid="roster-csv-import">
      <CardHeader>
        <h2 className="fa-auction-listone__title">Import CSV rose</h2>
      </CardHeader>
      <CardBody>
        <p>
          Scarica il modello, carica il file per l&apos;anteprima e conferma solo senza
          errori bloccanti. Nessuna scrittura avviene prima della conferma.
        </p>
        <div style={{ display: "flex", flexWrap: "wrap", gap: "0.75rem", marginTop: "0.75rem" }}>
          <Button
            type="button"
            variant="secondary"
            disabled={csvBusy}
            onClick={() => void onDownloadCsvTemplate()}
            data-testid="roster-csv-download"
          >
            Scarica modello CSV
          </Button>
          <Button
            type="button"
            variant="secondary"
            disabled={csvBusy}
            onClick={() => csvFileInputRef.current?.click()}
            data-testid="roster-csv-upload"
          >
            {csvBusy ? "Elaborazione…" : "Carica CSV"}
          </Button>
          <input
            ref={csvFileInputRef}
            type="file"
            accept=".csv,text/csv"
            hidden
            data-testid="roster-csv-file"
            onChange={(event) => {
              const file = event.target.files?.[0] ?? null;
              event.target.value = "";
              void onCsvFileSelected(file);
            }}
          />
          <Button
            type="button"
            disabled={csvBusy || !csvCanConfirm}
            onClick={() => void onConfirmCsvImport()}
            data-testid="roster-csv-confirm"
          >
            Conferma import
          </Button>
        </div>
        {csvMessage ? (
          <UiStatePanel state="success" title="Import CSV" message={csvMessage} testId="roster-csv-ok" />
        ) : null}
        {csvError ? (
          <UiStatePanel state="error" title="Import CSV" message={csvError} testId="roster-csv-error" />
        ) : null}
        {csvPreview ? (
          <div style={{ marginTop: "1rem" }} data-testid="roster-csv-preview">
            <p>
              Anteprima: {csvPreview.rowCount} righe · errori {csvPreview.errorCount} ·
              avvisi {csvPreview.warningCount}
            </p>
            <Table>
              <TableHead>
                <TableRow>
                  <TableHeaderCell>Riga</TableHeaderCell>
                  <TableHeaderCell>Squadra</TableHeaderCell>
                  <TableHeaderCell>Calciatore</TableHeaderCell>
                  <TableHeaderCell>Crediti</TableHeaderCell>
                  <TableHeaderCell>Stato</TableHeaderCell>
                  <TableHeaderCell>Dettaglio</TableHeaderCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {csvPreview.rows.map((row) => (
                  <TableRow key={row.rowNumber}>
                    <TableCell>{row.rowNumber}</TableCell>
                    <TableCell>{row.fantasyTeamName ?? row.squadra}</TableCell>
                    <TableCell>{row.athleteName ?? row.nome ?? "—"}</TableCell>
                    <TableCell>{row.crediti ?? "—"}</TableCell>
                    <TableCell>{row.status}</TableCell>
                    <TableCell>
                      {row.issues.map((issue) => issue.message).join(" · ") || "—"}
                      {row.status === "ambiguous" ? (
                        <select
                          aria-label={`Risolvi riga ${row.rowNumber}`}
                          data-testid={`roster-csv-resolve-${row.rowNumber}`}
                          value={csvResolutions[row.rowNumber] ?? ""}
                          onChange={(event) =>
                            onCsvResolutionChange(row.rowNumber, event.target.value)
                          }
                        >
                          <option value="">Seleziona calciatore…</option>
                          {row.candidates.map((candidate) => (
                            <option key={candidate.athleteId} value={candidate.athleteId}>
                              {candidate.canonicalName} (#{candidate.providerId})
                            </option>
                          ))}
                        </select>
                      ) : null}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        ) : null}
      </CardBody>
    </Card>
  );
}
