import type { RosterImportPreview } from "@fantappero/contracts";
import { Pressable, Text, View } from "react-native";
import { rosterStyles as styles } from "./rosterStyles";

export function RosterCsvImportCard({
  csvBusy,
  onDownloadTemplate,
  onExportRosters,
  onPickExcel,
  csvPreview,
  onConfirmCsvImport,
  csvMessage,
  csvError,
}: {
  csvBusy: boolean;
  onDownloadTemplate: () => void | Promise<void>;
  onExportRosters: () => void | Promise<void>;
  onPickExcel: () => void | Promise<void>;
  csvPreview: RosterImportPreview | null;
  onConfirmCsvImport: () => void | Promise<void>;
  csvMessage: string | null;
  csvError: string | null;
}) {
  return (
    <View style={styles.excelCard} testID="roster-excel-import">
      <Text style={styles.cardTitle}>Rose Excel</Text>
      <View style={styles.excelActions}>
        <Pressable
          style={[styles.creditsButton, csvBusy && styles.disabled]}
          disabled={csvBusy}
          onPress={() => void onDownloadTemplate()}
          testID="roster-excel-template"
        >
          <Text style={styles.creditsButtonLabel}>Modello</Text>
        </Pressable>
        <Pressable
          style={[styles.creditsButton, csvBusy && styles.disabled]}
          disabled={csvBusy}
          onPress={() => void onExportRosters()}
          testID="roster-excel-export"
        >
          <Text style={styles.creditsButtonLabel}>Esporta</Text>
        </Pressable>
        <Pressable
          style={[styles.creditsButton, csvBusy && styles.disabled]}
          disabled={csvBusy}
          onPress={() => void onPickExcel()}
          testID="roster-excel-upload"
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
      </View>
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
    </View>
  );
}
