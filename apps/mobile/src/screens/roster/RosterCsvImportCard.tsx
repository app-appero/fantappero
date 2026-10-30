import type { RosterImportPreview } from "@fantappero/contracts";
import { useState } from "react";
import { HScroll } from "../../components/HScroll";
import { Modal, Pressable, Text, View } from "react-native";
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
  onConfirmCsvImport: () => void | Promise<void>;
  csvMessage: string | null;
  csvError: string | null;
}) {
  const [exportOpen, setExportOpen] = useState(false);
  const [importOpen, setImportOpen] = useState(false);

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
          style={[styles.creditsButton, (csvBusy || !csvPreview?.canConfirm) && styles.disabled]}
          disabled={csvBusy || !csvPreview?.canConfirm}
          onPress={() => void onConfirmCsvImport()}
          testID="roster-excel-confirm"
        >
          <Text style={styles.creditsButtonLabel}>Conferma</Text>
        </Pressable>
      </HScroll>
      <Text style={styles.meta}>
        Nome del listone oppure solo il cognome, maiuscole indifferenti. Se non si trova, la riga
        non cambia la rosa.
      </Text>
      {csvPreview ? (
        <Text style={styles.meta} testID="roster-excel-preview">
          Anteprima: {csvPreview.rowCount} righe · errori {csvPreview.errorCount} · avvisi{" "}
          {csvPreview.warningCount}
        </Text>
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
