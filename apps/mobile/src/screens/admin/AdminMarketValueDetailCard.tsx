import {
  type AdminListoneEntry,
  type AdminMarketValueDetail,
  type AdminMarketValueSeasonDetail,
  formatPercentileOrdinal,
  formatValueNumber,
  formatWeightPercent,
  marketValueBaseSentence,
  marketValueBudgetSentence,
  marketValueCreditsForBudget,
  marketValueCurveSentence,
  marketValueExcludedText,
  marketValueIndexSentence,
  marketValueRolePlural,
  marketValueSeasonName,
  marketValueSeasonSentence,
  marketValueSourceLabel,
  marketValueStatusText,
} from "@fantappero/contracts";
import { theme } from "@fantappero/ui/theme";
import { useMemo, useRef, useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { adminUiStyles as styles } from "../../admin/adminUiStyles";
import { parseValueDetailBudget, valueDetailCandidates } from "../../admin/marketValueDetail";
import { fetchMarketValueDetail } from "../../api/admin";
import { ApiError } from "../../api/client";
import { AppTextInput as TextInput } from "../../components/AppTextInput";
import { UiStatePanel } from "../../components/UiStatePanel";
import { getApiErrorMessage, useAuthSession } from "../../session/DemoSessionContext";
import { lazyStyles } from "../../theme/lazyStyles";
import { foldSearchText } from "../roster/listoneFilter";

type Row = { label: string; value: (season: AdminMarketValueSeasonDetail) => string };

function numberOrDash(value: number | null): string {
  return value === null ? "—" : formatValueNumber(value);
}

function seasonRows(detail: AdminMarketValueDetail): Row[] {
  return [
    { label: "Fonte", value: (s) => (s.source ? marketValueSourceLabel(s.source) : "—") },
    { label: "Competizioni", value: (s) => (s.competitions.length > 0 ? s.competitions.join(", ") : "—") },
    { label: "Presenze con voto", value: (s) => (s.hasData || s.appearances > 0 ? String(s.appearances) : "—") },
    { label: "Media", value: (s) => numberOrDash(s.average) },
    { label: `Media dei ${marketValueRolePlural(detail.role)}`, value: (s) => numberOrDash(s.roleAverage) },
    { label: "Media ristretta", value: (s) => numberOrDash(s.shrunkAverage) },
    {
      label: "Percentile",
      value: (s) =>
        s.percentile === null
          ? s.isCurrent
            ? "—"
            : `${formatValueNumber(s.indexUsed)} (senza dati)`
          : `${formatPercentileOrdinal(s.percentile)}${s.rank !== null && s.poolSize !== null ? ` (${s.rank}° di ${s.poolSize})` : ""}`,
    },
    { label: "Peso", value: (s) => formatWeightPercent(s.weight) },
    { label: "Contributo a p", value: (s) => formatValueNumber(s.contribution) },
  ];
}

/**
 * Pannello operatore → Listone → «Dettaglio del Valore» (1.4), come sul sito: cerca un
 * calciatore nel listone già caricato dalla schermata, poi la tabella per stagione e il calcolo
 * in italiano (`docs/operations/valore_di_mercato_e_storico.md` § 8). Solo operatori
 * (`global:operate`), come il resto del pannello.
 */
export function AdminMarketValueDetailCard({
  entries,
  seasonYear,
}: {
  entries: AdminListoneEntry[];
  seasonYear: number | null;
}) {
  const { accessToken, can } = useAuthSession();
  const isOperator = can(["global:operate"]);
  const [query, setQuery] = useState("");
  const [budgetText, setBudgetText] = useState("1000");
  const [detail, setDetail] = useState<AdminMarketValueDetail | null>(null);
  const [loadingId, setLoadingId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const requestRef = useRef(0);

  const candidates = useMemo(
    () => valueDetailCandidates(entries, query, foldSearchText),
    [entries, query],
  );

  if (!isOperator) {
    return null;
  }

  const budget = parseValueDetailBudget(budgetText);
  const otherBudget = detail !== null && budget !== null && budget !== detail.referenceBudget ? budget : null;

  async function onPick(entry: AdminListoneEntry) {
    if (seasonYear === null) {
      setError("Inserisci un anno stagione valido nel listone.");
      return;
    }
    if (!accessToken) {
      setError("Sessione non disponibile. Accedi di nuovo.");
      return;
    }
    const request = ++requestRef.current;
    setLoadingId(entry.athleteId);
    setError(null);
    try {
      const loaded = await fetchMarketValueDetail(accessToken, entry.athleteId, seasonYear);
      if (request === requestRef.current) {
        setDetail(loaded);
      }
    } catch (loadError) {
      if (request === requestRef.current) {
        setDetail(null);
        setError(
          loadError instanceof ApiError && loadError.status === 404
            ? "Il calciatore non è nel listone di questa stagione."
            : getApiErrorMessage(loadError, "Impossibile leggere il dettaglio del Valore."),
        );
      }
    } finally {
      if (request === requestRef.current) {
        setLoadingId(null);
      }
    }
  }

  const statusText = detail ? marketValueStatusText(detail) : null;

  return (
    <View style={styles.section} testID="admin-value-detail-card">
      <Text style={styles.sectionTitle}>Dettaglio del Valore</Text>
      <Text style={styles.meta}>
        Cerca un calciatore del listone per vedere come si arriva al suo Valore: stagione per
        stagione, poi il calcolo finale. Mostra l'ultimo ricalcolo; non chiama il fornitore.
      </Text>
      <View style={local.fields}>
        <View style={local.queryField}>
          <Text style={styles.meta}>Cerca calciatore</Text>
          <TextInput
            style={styles.input}
            value={query}
            onChangeText={setQuery}
            placeholder="Nome o club"
            autoCapitalize="none"
            autoCorrect={false}
            testID="admin-value-detail-query"
          />
        </View>
        <View style={local.budgetField}>
          <Text style={styles.meta}>Budget lega</Text>
          <TextInput
            style={styles.input}
            value={budgetText}
            onChangeText={setBudgetText}
            keyboardType="numeric"
            maxLength={6}
            accessibilityLabel="Budget della lega"
            testID="admin-value-detail-budget"
          />
        </View>
      </View>

      {entries.length === 0 ? (
        <Text style={styles.meta}>Il listone della stagione non è caricato: la ricerca usa i calciatori qui sotto.</Text>
      ) : null}
      {candidates.length > 0 ? (
        <View style={local.results} testID="admin-value-detail-results">
          {candidates.map((entry) => {
            const selected = detail?.athleteId === entry.athleteId;
            return (
              <Pressable
                key={entry.athleteId}
                style={[styles.chip, selected && styles.chipActive, loadingId !== null && styles.disabled]}
                disabled={loadingId !== null}
                onPress={() => void onPick(entry)}
                accessibilityRole="button"
                testID={`admin-value-detail-pick-${entry.athleteId}`}
              >
                <Text style={[styles.chipLabel, selected && styles.chipLabelActive]} numberOfLines={2}>
                  {loadingId === entry.athleteId ? "Carico… " : ""}
                  {entry.officialRole} · {entry.canonicalName}
                  {entry.clubName ? ` · ${entry.clubName}` : ""}
                </Text>
              </Pressable>
            );
          })}
        </View>
      ) : null}
      {query.trim().length >= 2 && candidates.length === 0 && entries.length > 0 ? (
        <Text style={styles.meta}>Nessun calciatore del listone con questo nome o club.</Text>
      ) : null}

      {error ? (
        <UiStatePanel state="error" title="Dettaglio non disponibile" message={error} testID="admin-value-detail-error" />
      ) : null}

      {detail ? (
        <View style={local.result} testID="admin-value-detail-result">
          <View style={local.summary}>
            <Text style={local.summaryText}>
              <Text style={local.strong}>{detail.canonicalName}</Text> ({detail.role}
              {detail.clubName ? `, ${detail.clubName}` : ""}): Valore{" "}
              <Text style={local.strong}>
                {detail.referenceCredits} {detail.referenceCredits === 1 ? "credito" : "crediti"}
              </Text>{" "}
              a budget {detail.referenceBudget}
              {otherBudget !== null
                ? `, ${marketValueCreditsForBudget(detail.referenceValue, otherBudget, detail.referenceBudget)} a budget ${otherBudget}`
                : ""}{" "}
              · p = {formatValueNumber(detail.valueIndex)}
            </Text>
          </View>
          {statusText ? (
            <UiStatePanel
              state="empty"
              title={detail.status === "outdated" ? "Dettaglio incompleto" : "Valore non ancora calcolato"}
              message={statusText}
              testID="admin-value-detail-status"
            />
          ) : null}

          <View testID="admin-value-detail-table">
            <View style={[styles.tableRow, styles.tableHeaderRow]}>
              <Text style={[styles.tableCell, styles.tableHeaderCell, local.labelCell]} />
              {detail.seasons.map((season) => (
                <Text key={season.slot} style={[styles.tableCell, styles.tableHeaderCell]}>
                  {marketValueSeasonName(season.seasonYear)}
                  {season.isCurrent ? "\nin corso" : ""}
                </Text>
              ))}
            </View>
            {seasonRows(detail).map((row) => (
              <View key={row.label} style={[styles.tableRow, local.tableRow]}>
                <Text style={[styles.tableCell, styles.tableHeaderCell, local.labelCell]}>{row.label}</Text>
                {detail.seasons.map((season) => (
                  <Text key={season.slot} style={[styles.tableCell, local.valueCell]}>
                    {row.value(season)}
                  </Text>
                ))}
              </View>
            ))}
          </View>

          <Text style={local.subtitle}>Come si arriva al Valore</Text>
          <View style={local.steps} testID="admin-value-detail-steps">
            {detail.seasons.map((season, index) => {
              const excluded = marketValueExcludedText(season);
              return (
                <View key={season.slot}>
                  <Text style={local.step}>
                    {index + 1}. {marketValueSeasonSentence(season, detail.role, detail.missingSeasonIndex)}
                  </Text>
                  {excluded ? <Text style={styles.meta}>{excluded}</Text> : null}
                </View>
              );
            })}
            <Text style={local.step}>4. {marketValueIndexSentence(detail)}</Text>
            <Text style={local.step}>5. {marketValueCurveSentence(detail)}</Text>
            {otherBudget !== null ? (
              <Text style={local.step}>6. {marketValueBudgetSentence(detail, otherBudget)}</Text>
            ) : null}
          </View>
          <Text style={styles.meta}>
            {marketValueBaseSentence(detail)}. Media ristretta = (n × media + {detail.shrinkAppearances} ×
            media del ruolo) / (n + {detail.shrinkAppearances}); una stagione passata senza dati vale{" "}
            {formatValueNumber(detail.missingSeasonIndex)}; la stagione in corso pesa fino al 50% (pieno a{" "}
            {detail.currentFullWeightAppearances} partite con voto), il resto va alle passate 30:20.
            {detail.version ? ` Formula ${detail.version}.` : ""}
          </Text>
        </View>
      ) : null}
    </View>
  );
}

const local = lazyStyles(() =>
  StyleSheet.create({
    fields: {
      flexDirection: "row",
      alignItems: "flex-end",
      gap: theme.spacing.sm,
    },
    queryField: {
      flex: 1,
      minWidth: 0,
      gap: theme.spacing.xs,
    },
    budgetField: {
      width: 96,
      gap: theme.spacing.xs,
    },
    results: {
      flexDirection: "row",
      flexWrap: "wrap",
      gap: theme.spacing.xs,
    },
    result: {
      gap: theme.spacing.sm,
    },
    summary: {
      padding: theme.spacing.sm,
      borderRadius: theme.radius.md,
      borderWidth: 1,
      borderColor: theme.colors.border,
    },
    summaryText: {
      color: theme.colors.foreground,
      fontSize: theme.typography.fontSize.sm,
      lineHeight: 20,
    },
    strong: {
      fontWeight: theme.typography.fontWeight.semibold,
    },
    tableRow: {
      alignItems: "flex-start",
    },
    labelCell: {
      flex: 1.3,
    },
    valueCell: {
      fontVariant: ["tabular-nums"],
    },
    subtitle: {
      color: theme.colors.foreground,
      fontSize: theme.typography.fontSize.md,
      fontWeight: theme.typography.fontWeight.semibold,
    },
    steps: {
      gap: theme.spacing.xs,
    },
    step: {
      color: theme.colors.foreground,
      fontSize: theme.typography.fontSize.sm,
      lineHeight: 20,
    },
  }),
);
