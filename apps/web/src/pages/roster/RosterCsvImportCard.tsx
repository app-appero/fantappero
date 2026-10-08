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
import { AthleteName } from "../../athletes/AthleteCard";

function excelRowStatusLabel(status: string): string {
  if (status === "skipped") {
    return "ignorato";
  }
  if (status === "ok") {
    return "pronto";
  }
  if (status === "error") {
    return "errore";
  }
  if (status === "ambiguous") {
    return "ambiguo";
  }
  return status;
}

export function RosterCsvImportCard({
  csvBusy,
  onDownloadCsvTemplate,
  onDownloadRosterExport,
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
  onDownloadRosterExport: () => void | Promise<void>;
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
    <Card className="fa-roster-excel" data-testid="roster-excel-import">
      <CardHeader>
        <h2 className="fa-auction-listone__title">Rose Excel</h2>
      </CardHeader>
      <CardBody>
        <div className="fa-roster-excel__actions">
          <Button
            type="button"
            variant="secondary"
            disabled={csvBusy}
            onClick={() => void onDownloadCsvTemplate()}
            data-testid="roster-excel-template"
          >
            Scarica modello
          </Button>
          <Button
            type="button"
            variant="secondary"
            disabled={csvBusy}
            onClick={() => void onDownloadRosterExport()}
            data-testid="roster-excel-export"
          >
            Esporta rosa
          </Button>
          <Button
            type="button"
            variant="secondary"
            disabled={csvBusy}
            onClick={() => csvFileInputRef.current?.click()}
            data-testid="roster-excel-upload"
          >
            {csvBusy ? "Elaborazione…" : "Importa Excel"}
          </Button>
          <input
            ref={csvFileInputRef}
            type="file"
            accept=".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            hidden
            data-testid="roster-excel-file"
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
            data-testid="roster-excel-confirm"
          >
            Conferma import
          </Button>
        </div>
        <p className="fa-roster-excel__hint">
          Il file ha solo Calciatore e Crediti, per la squadra selezionata. Se un nome non è nel
          listone, quella riga non cambia la rosa.
        </p>
        {csvMessage ? (
          <UiStatePanel state="success" title="Rose Excel" message={csvMessage} testId="roster-excel-ok" />
        ) : null}
        {csvError ? (
          <UiStatePanel state="error" title="Rose Excel" message={csvError} testId="roster-excel-error" />
        ) : null}
        {csvPreview ? (
          <div className="fa-roster-excel__preview" data-testid="roster-excel-preview">
            <p>
              Anteprima: {csvPreview.rowCount} righe · errori {csvPreview.errorCount} · avvisi{" "}
              {csvPreview.warningCount}
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
                    <TableCell>
                      <AthleteName athleteId={row.athleteId}>{row.athleteName ?? row.nome ?? "—"}</AthleteName>
                    </TableCell>
                    <TableCell>{row.crediti ?? "—"}</TableCell>
                    <TableCell>{excelRowStatusLabel(row.status)}</TableCell>
                    <TableCell>
                      {row.issues.map((issue) => issue.message).join(" · ") || "—"}
                      {row.status === "ambiguous" ? (
                        <select
                          aria-label={`Risolvi riga ${row.rowNumber}`}
                          data-testid={`roster-excel-resolve-${row.rowNumber}`}
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
