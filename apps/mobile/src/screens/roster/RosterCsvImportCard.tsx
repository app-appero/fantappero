import type { RosterImportPreview } from "@fantappero/contracts";
import {
  canConfirmRosterImport,
  describeRosterImportCandidate,
  rosterImportAmbiguousCount,
  rosterImportAmbiguousRows,
} from "@fantappero/contracts";
import { useState } from "react";
import { HScroll } from "../../components/HScroll";
import { Modal, Pressable, Text, View } from "react-native";
import type { CsvResolutions } from "./csvImportResolutions";
import { rosterStyles as styles } from "./rosterStyles";

function OptionSheet({
  visible,
  onClose,
  title,
  testID,
  options,
}: {
  visible: boolean;
  onClose: () => void;
  title: string;
  testID: string;
  options: Array<{ label: string; onPress: () => void; testID: string }>;
}) {
  return (
    <Modal visible={visible} transparent animationType="slide" onRequestClose={onClose}>
      <Pressable style={styles.adjustBackdrop} onPress={onClose}>
        <Pressable style={styles.adjustSheet} onPress={() => undefined} testID={testID}>
          <Text style={styles.blockTitle}>{title}</Text>
          <View style={{ gap: 6 }}>
            {options.map((option) => (
              <Pressable
                key={option.testID}
                style={styles.moveRow}
                onPress={() => {
                  onClose();
                  option.onPress();
                }}
                testID={option.testID}
              >
                <Text style={[styles.moveTitle, { flex: 1 }]}>{option.label}</Text>
              </Pressable>
            ))}
          </View>
        </Pressable>
      </Pressable>
    </Modal>
  );
}

export function RosterCsvImportCard({
  csvBusy,
  adminTeamName,
  onDownloadTemplate,
  onExportRosters,
  onExportAllRosters,
  onPickExcel,
  onPickBulkExcel,
  csvPreview,
  csvResolutions,
  onCsvResolutionPress,
  onConfirmCsvImport,
  csvMessage,
  csvError,
}: {
  csvBusy: boolean;
  /** Nome dell'allenatore/squadra selezionata lato admin, per etichettare le opzioni "corrente". */
  adminTeamName?: string | null;
  onDownloadTemplate: () => void | Promise<void>;
  onExportRosters: () => void | Promise<void>;
  onExportAllRosters: () => void | Promise<void>;
  onPickExcel: () => void | Promise<void>;
  onPickBulkExcel: () => void | Promise<void>;
  csvPreview: RosterImportPreview | null;
  /** Calciatore scelto per ogni nome ambiguo (numero di riga → athleteId). */
  csvResolutions: CsvResolutions;
  onCsvResolutionPress: (rowNumber: number, athleteId: string) => void;
  onConfirmCsvImport: () => void | Promise<void>;
  csvMessage: string | null;
  csvError: string | null;
}) {
  const [exportOpen, setExportOpen] = useState(false);
  const [importOpen, setImportOpen] = useState(false);
  // Nomi di più calciatori: avvisi da risolvere scegliendo il candidato, non errori
  // (QA 19-20/11). Stessa regola del web per abilitare la conferma.
  const ambiguousRows = csvPreview ? rosterImportAmbiguousRows(csvPreview) : [];
  const ambiguousCount = csvPreview ? rosterImportAmbiguousCount(csvPreview) : 0;
  const canConfirm = canConfirmRosterImport(csvPreview, csvResolutions);

  return (
    <View style={styles.excelCard} testID="roster-excel-import">
      <Text style={styles.cardTitle}>Rose Excel</Text>
      <HScroll>
        <Pressable
          style={[styles.creditsButton, csvBusy && styles.disabled]}
          disabled={csvBusy}
          onPress={() => setExportOpen(true)}
          testID="roster-excel-export-open"
        >
          <Text style={styles.creditsButtonLabel}>Esporta</Text>
        </Pressable>
        <Pressable
          style={[styles.creditsButton, csvBusy && styles.disabled]}
          disabled={csvBusy}
          onPress={() => setImportOpen(true)}
          testID="roster-excel-upload-open"
        >
          <Text style={styles.creditsButtonLabel}>{csvBusy ? "…" : "Importa"}</Text>
        </Pressable>
        <Pressable
          style={[styles.creditsButton, (csvBusy || !canConfirm) && styles.disabled]}
          disabled={csvBusy || !canConfirm}
          onPress={() => void onConfirmCsvImport()}
          testID="roster-excel-confirm"
        >
          <Text style={styles.creditsButtonLabel}>Conferma</Text>
        </Pressable>
      </HScroll>
      <Text style={styles.meta}>
        Nome del listone oppure solo il cognome, maiuscole e accenti indifferenti. Se non si
        trova, la riga non cambia la rosa; se è di più calciatori, scegli quello giusto qui sotto.
      </Text>
      {csvPreview ? (
        <Text style={styles.meta} testID="roster-excel-preview">
          Anteprima: {csvPreview.rowCount} righe · errori {csvPreview.errorCount}
          {ambiguousCount > 0 ? ` · nomi ambigui ${ambiguousCount}` : ""} · avvisi{" "}
          {csvPreview.warningCount}
        </Text>
      ) : null}
      {ambiguousRows.length > 0 ? (
        <View testID="roster-excel-ambiguous">
          <Text style={styles.meta}>
            {ambiguousRows.length === 1
              ? "Un nome corrisponde a più calciatori: scegli quello giusto (ruolo e squadra) e poi conferma."
              : `${ambiguousRows.length} nomi corrispondono a più calciatori: scegli quelli giusti (ruolo e squadra) e poi conferma.`}
          </Text>
          {ambiguousRows.map((row) => (
            <View key={row.rowNumber} testID={`roster-excel-resolve-${row.rowNumber}`}>
              <Text style={styles.fieldLabel}>
                Riga {row.rowNumber} · «{row.nome}»
              </Text>
              {row.candidates.map((candidate) => {
                const selected = csvResolutions[row.rowNumber] === candidate.athleteId;
                return (
                  <Pressable
                    key={candidate.athleteId}
                    style={[styles.moveRow, selected && styles.candidateRowSelected]}
                    onPress={() => onCsvResolutionPress(row.rowNumber, candidate.athleteId)}
                    accessibilityRole="radio"
                    accessibilityState={{ checked: selected, disabled: csvBusy }}
                    disabled={csvBusy}
                    testID={`roster-excel-candidate-${row.rowNumber}-${candidate.athleteId}`}
                  >
                    <View style={{ flex: 1 }}>
                      <Text style={styles.moveTitle}>{candidate.canonicalName}</Text>
                      <Text style={styles.moveDate}>{describeRosterImportCandidate(candidate)}</Text>
                    </View>
                    {selected ? <Text style={styles.moveTitle}>✓</Text> : null}
                  </Pressable>
                );
              })}
            </View>
          ))}
        </View>
      ) : null}
      {csvMessage ? (
        <Text style={styles.ok} testID="roster-excel-ok">
          {csvMessage}
        </Text>
      ) : null}
      {csvError ? (
        <Text style={styles.error} testID="roster-excel-error">
          {csvError}
        </Text>
      ) : null}

      <OptionSheet
        visible={exportOpen}
        onClose={() => setExportOpen(false)}
        title="Esporta rose"
        testID="roster-excel-export-sheet"
        options={[
          { label: "Scarica modello", onPress: () => void onDownloadTemplate(), testID: "roster-excel-template" },
          {
            label: `Esporta rosa corrente${adminTeamName ? ` (${adminTeamName})` : ""}`,
            onPress: () => void onExportRosters(),
            testID: "roster-excel-export",
          },
          {
            label: "Esporta tutte le rose della lega",
            onPress: () => void onExportAllRosters(),
            testID: "roster-excel-export-all",
          },
        ]}
      />
      <OptionSheet
        visible={importOpen}
        onClose={() => setImportOpen(false)}
        title="Importa rose"
        testID="roster-excel-import-sheet"
        options={[
          {
            label: `Importa per ${adminTeamName ? adminTeamName : "la squadra selezionata"}`,
            onPress: () => void onPickExcel(),
            testID: "roster-excel-upload",
          },
          {
            label: "Importa massivo (tutta la lega)",
            onPress: () => void onPickBulkExcel(),
            testID: "roster-excel-upload-all",
          },
        ]}
      />
    </View>
  );
}
