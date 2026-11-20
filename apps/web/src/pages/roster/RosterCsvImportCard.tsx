import type { RosterImportPreview } from "@fantappero/contracts";
import { describeRosterImportCandidate, rosterImportAmbiguousCount } from "@fantappero/contracts";
import {
  Button,
  Card,
  CardBody,
  CardHeader,
  Modal,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeaderCell,
  TableRow,
  UiStatePanel,
} from "@fantappero/ui";
import { useState, type RefObject } from "react";
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
  adminTeamName,
  onDownloadCsvTemplate,
  onDownloadRosterExport,
  onDownloadAllRostersExport,
  csvFileInputRef,
  onCsvFileSelected,
  bulkCsvFileInputRef,
  onBulkCsvFileSelected,
  csvCanConfirm,
  onConfirmCsvImport,
  csvMessage,
  csvError,
  csvPreview,
  csvResolutions,
  onCsvResolutionChange,
}: {
  csvBusy: boolean;
  /** Nome dell'allenatore/squadra selezionata lato admin, per etichettare le opzioni "corrente". */
  adminTeamName?: string | null;
  onDownloadCsvTemplate: () => void | Promise<void>;
  onDownloadRosterExport: () => void | Promise<void>;
  onDownloadAllRostersExport: () => void | Promise<void>;
  csvFileInputRef: RefObject<HTMLInputElement | null>;
  onCsvFileSelected: (file: File | null) => void | Promise<void>;
  bulkCsvFileInputRef: RefObject<HTMLInputElement | null>;
  onBulkCsvFileSelected: (file: File | null) => void | Promise<void>;
  csvCanConfirm: boolean;
  onConfirmCsvImport: () => void | Promise<void>;
  csvMessage: string | null;
  csvError: string | null;
  csvPreview: RosterImportPreview | null;
  csvResolutions: Record<number, string>;
  onCsvResolutionChange: (rowNumber: number, athleteId: string) => void;
}) {
  const [exportModalOpen, setExportModalOpen] = useState(false);
  const [importModalOpen, setImportModalOpen] = useState(false);
  const currentLabel = adminTeamName ? `(${adminTeamName})` : "";
  // Nomi di più calciatori: avvisi da risolvere, non errori (QA 19-20/11).
  const ambiguousCount = csvPreview ? rosterImportAmbiguousCount(csvPreview) : 0;

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
            onClick={() => setExportModalOpen(true)}
            data-testid="roster-excel-export-open"
          >
            Esporta rosa
          </Button>
          <Button
            type="button"
            variant="secondary"
            disabled={csvBusy}
            onClick={() => setImportModalOpen(true)}
            data-testid="roster-excel-upload-open"
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
          <input
            ref={bulkCsvFileInputRef}
            type="file"
            accept=".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            hidden
            data-testid="roster-excel-file-all"
            onChange={(event) => {
              const file = event.target.files?.[0] ?? null;
              event.target.value = "";
              void onBulkCsvFileSelected(file);
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
          Il file ha solo Calciatore e Crediti, per la squadra selezionata. Vale il nome del
          listone oppure solo il cognome; maiuscole, minuscole e accenti non contano. Se non si
          trova, quella riga non cambia la rosa; se è di più calciatori, scegli quello giusto
          nell'anteprima prima di confermare.
        </p>

        <Modal
          open={exportModalOpen}
          onClose={() => setExportModalOpen(false)}
          title="Esporta rose"
        >
          <div className="fa-roster-excel__modal-options">
            <Button
              type="button"
              variant="secondary"
              disabled={csvBusy}
              onClick={() => {
                setExportModalOpen(false);
                void onDownloadCsvTemplate();
              }}
              data-testid="roster-excel-template"
            >
              Scarica modello
            </Button>
            <Button
              type="button"
              variant="secondary"
              disabled={csvBusy}
              onClick={() => {
                setExportModalOpen(false);
                void onDownloadRosterExport();
              }}
              data-testid="roster-excel-export"
            >
              Esporta rosa corrente {currentLabel}
            </Button>
            <Button
              type="button"
              variant="secondary"
              disabled={csvBusy}
              onClick={() => {
                setExportModalOpen(false);
                void onDownloadAllRostersExport();
              }}
              data-testid="roster-excel-export-all"
            >
              Esporta tutte le rose della lega
            </Button>
          </div>
          <p className="fa-roster-excel__hint">
            L'export massivo scarica un unico Excel con un foglio per allenatore.
          </p>
        </Modal>

        <Modal
          open={importModalOpen}
          onClose={() => setImportModalOpen(false)}
          title="Importa rose"
        >
          <div className="fa-roster-excel__modal-options">
            <Button
              type="button"
              variant="secondary"
              disabled={csvBusy}
              onClick={() => {
                setImportModalOpen(false);
                csvFileInputRef.current?.click();
              }}
              data-testid="roster-excel-upload"
            >
              Importa per {adminTeamName ? adminTeamName : "la squadra selezionata"}
            </Button>
            <Button
              type="button"
              variant="secondary"
              disabled={csvBusy}
              onClick={() => {
                setImportModalOpen(false);
                bulkCsvFileInputRef.current?.click();
              }}
              data-testid="roster-excel-upload-all"
            >
              Importa massivo (tutta la lega)
            </Button>
          </div>
          <p className="fa-roster-excel__hint">
            Nell'import massivo il nome di ogni foglio deve combaciare esattamente col nome
            dell'allenatore: i fogli senza corrispondenza vengono ignorati, nessuna rosa cambia.
            Dopo l'anteprima, conferma con "Conferma import" qui sotto.
          </p>
        </Modal>

        {csvMessage ? (
          <UiStatePanel state="success" title="Rose Excel" message={csvMessage} testId="roster-excel-ok" />
        ) : null}
        {csvError ? (
          <UiStatePanel state="error" title="Rose Excel" message={csvError} testId="roster-excel-error" />
        ) : null}
        {csvPreview ? (
          <div className="fa-roster-excel__preview" data-testid="roster-excel-preview">
            <p data-testid="roster-excel-preview-counts">
              Anteprima: {csvPreview.rowCount} righe · errori {csvPreview.errorCount}
              {ambiguousCount > 0 ? ` · nomi ambigui ${ambiguousCount}` : ""} · avvisi{" "}
              {csvPreview.warningCount}
            </p>
            {ambiguousCount > 0 ? (
              <p className="fa-roster-excel__hint" data-testid="roster-excel-ambiguous-hint">
                {ambiguousCount === 1
                  ? "Un nome corrisponde a più calciatori: scegli quello giusto (ruolo e squadra) e poi conferma."
                  : `${ambiguousCount} nomi corrispondono a più calciatori: scegli quelli giusti (ruolo e squadra) e poi conferma.`}
              </p>
            ) : null}
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
                            <option
                              key={candidate.athleteId}
                              value={candidate.athleteId}
                              data-testid={`roster-excel-candidate-${row.rowNumber}-${candidate.athleteId}`}
                            >
                              {`${candidate.canonicalName} — ${describeRosterImportCandidate(candidate)}`}
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
