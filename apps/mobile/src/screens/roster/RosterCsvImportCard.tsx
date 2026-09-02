import type { RosterImportPreview } from "@fantappero/contracts";
import { Pressable, Text, TextInput, View } from "react-native";
import { rosterStyles as styles } from "./rosterStyles";

export function RosterCsvImportCard({
  csvText,
  onCsvTextChange,
  csvBusy,
  onPreviewCsvText,
  csvPreview,
  onConfirmCsvImport,
  csvMessage,
  csvError,
}: {
  csvText: string;
  onCsvTextChange: (value: string) => void;
  csvBusy: boolean;
  onPreviewCsvText: () => void | Promise<void>;
  csvPreview: RosterImportPreview | null;
  onConfirmCsvImport: () => void | Promise<void>;
  csvMessage: string | null;
  csvError: string | null;
}) {
  return (
    <View style={styles.card} testID="roster-csv-import">
      <Text style={styles.cardTitle}>Import CSV rose</Text>
      <Text style={styles.meta}>
        Incolla il CSV (colonne squadra,provider_id,nome,crediti), genera anteprima e conferma
        solo senza errori.
      </Text>
      <TextInput
        style={[styles.input, styles.csvInput]}
        multiline
        value={csvText}
        onChangeText={onCsvTextChange}
        editable={!csvBusy}
        testID="roster-csv-text"
        autoCapitalize="none"
        autoCorrect={false}
      />
      <Pressable
        style={[styles.button, csvBusy && styles.disabled]}
        disabled={csvBusy}
        onPress={() => void onPreviewCsvText()}
        testID="roster-csv-preview-btn"
      >
        <Text style={styles.buttonLabel}>{csvBusy ? "Elaborazione…" : "Anteprima CSV"}</Text>
      </Pressable>
      <Pressable
        style={[styles.button, (csvBusy || !csvPreview?.canConfirm) && styles.disabled]}
        disabled={csvBusy || !csvPreview?.canConfirm}
        onPress={() => void onConfirmCsvImport()}
        testID="roster-csv-confirm"
      >
        <Text style={styles.buttonLabel}>Conferma import</Text>
      </Pressable>
      {csvPreview ? (
        <Text style={styles.meta} testID="roster-csv-preview">
          Anteprima: {csvPreview.rowCount} righe · errori {csvPreview.errorCount} · avvisi{" "}
          {csvPreview.warningCount}
        </Text>
      ) : null}
      {csvMessage ? (
        <Text style={styles.ok} testID="roster-csv-ok">
          {csvMessage}
        </Text>
      ) : null}
      {csvError ? (
        <Text style={styles.error} testID="roster-csv-error">
          {csvError}
        </Text>
      ) : null}
    </View>
  );
}
