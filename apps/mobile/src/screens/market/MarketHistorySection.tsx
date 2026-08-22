import type { FantasyTeamSummary, MarketHistoryCategory } from "@fantappero/contracts";
import { Pressable, Text, View } from "react-native";
import { OptionPicker } from "../../components/OptionPicker";
import { UiStatePanel } from "../../components/UiStatePanel";
import { HISTORY_CATEGORY_OPTIONS } from "../../market/marketLabels";
import { marketUiStyles as styles } from "../../market/marketUiStyles";
import type { useMarketHistory } from "../../market/useMarketHistory";

const ALL_CATEGORIES_OPTION = { value: "", label: "Tutte le categorie" };
const ALL_TEAMS_OPTION = { value: "", label: "Tutte le squadre" };

/** Storico mercato filtrabile e paginato (EP08-08 / FR-MKT-04). */
export function MarketHistorySection({
  history,
  teams,
}: {
  history: ReturnType<typeof useMarketHistory>;
  teams: FantasyTeamSummary[];
}) {
  return (
    <View style={styles.section} testID="wireframe-region-market-history">
      <Text style={styles.sectionTitle}>Storico mercato</Text>

      <View style={styles.rowActions}>
        <OptionPicker
          label="Categoria"
          options={[ALL_CATEGORIES_OPTION, ...HISTORY_CATEGORY_OPTIONS]}
          value={history.category ?? ""}
          onChange={(value) => history.setCategory(value as MarketHistoryCategory | "")}
          placeholder="Tutte le categorie"
          testID="market-history-category"
        />
        <OptionPicker
          label="Squadra"
          options={[ALL_TEAMS_OPTION, ...teams.map((row) => ({ value: row.id, label: row.name }))]}
          value={history.fantasyTeamId}
          onChange={history.setFantasyTeamId}
          placeholder="Tutte le squadre"
          testID="market-history-team"
        />
      </View>

      {history.loading ? (
        <UiStatePanel
          state="loading"
          title="Caricamento storico"
          message="Recupero gli eventi di mercato…"
          testID="market-history-loading"
        />
      ) : null}

      {!history.loading && history.loadError ? (
        <UiStatePanel
          state="error"
          title="Storico non disponibile"
          message={history.loadError}
          testID="market-history-error"
        />
      ) : null}

      {!history.loading && !history.loadError && history.items.length === 0 ? (
        <UiStatePanel
          state="empty"
          title="Nessun evento"
          message="Non ci sono eventi di mercato per i filtri selezionati."
          testID="market-history-empty"
        />
      ) : null}

      {!history.loading && !history.loadError && history.items.length > 0 ? (
        <>
          <View testID="market-history-list">
            {history.items.map((entry) => (
              <Text
                key={entry.id}
                style={styles.meta}
                testID={`market-history-entry-${entry.id}`}
              >
                [{entry.category}] {entry.action} — {new Date(entry.occurredAt).toLocaleString("it-IT")}
              </Text>
            ))}
          </View>
          <View style={styles.rowActions}>
            <Pressable
              style={[styles.secondaryButton, history.page <= 1 && styles.disabled]}
              disabled={history.page <= 1}
              onPress={() => history.goToPage(history.page - 1)}
              testID="market-history-prev-page"
            >
              <Text style={styles.secondaryButtonLabel}>Pagina precedente</Text>
            </Pressable>
            <Text style={styles.meta}>
              Pagina {history.page} di {history.totalPages} ({history.total} eventi)
            </Text>
            <Pressable
              style={[styles.secondaryButton, history.page >= history.totalPages && styles.disabled]}
              disabled={history.page >= history.totalPages}
              onPress={() => history.goToPage(history.page + 1)}
              testID="market-history-next-page"
            >
              <Text style={styles.secondaryButtonLabel}>Pagina successiva</Text>
            </Pressable>
          </View>
        </>
      ) : null}
    </View>
  );
}
