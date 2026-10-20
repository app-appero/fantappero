import type { LeagueListoneEntry, LeagueSummary } from "@fantappero/contracts";
import { Pressable, Text, View } from "react-native";
import { AthleteChooser } from "../../components/AthleteChooser";
import { UiStatePanel } from "../../components/UiStatePanel";
import { marketUiStyles as styles } from "../../market/marketUiStyles";

// The "Tutti" tab returns the whole listone (several hundred players).
// Rendering that as plain Views inside a ScrollView (no FlatList — see
// RosterAdminManualCard.tsx for why) mounts too many native views at once
// and gets the app killed for excessive memory use on a real device.

/** Official listone with role tabs — read-only reference table shown below the bid panel (EP08-01/02). */
export function AuctionListone({
  entries,
  loading,
  loadError,
  onRetry,
  activeLeagueId,
  activeLeague,
  ownedAthleteIds,
  bidding = false,
}: {
  entries: LeagueListoneEntry[];
  loading: boolean;
  loadError: string | null;
  onRetry: () => void;
  activeLeagueId: string | null;
  activeLeague: LeagueSummary | null;
  ownedAthleteIds: Set<string>;
  /** Con l'asta aperta l'elenco per scegliere sta nel pannello «Nuova offerta». */
  bidding?: boolean;
}) {

  return (
    <View style={styles.section} testID="auction-listone-card">
      <Text style={styles.sectionTitle}>Listone ufficiale</Text>
      <Text style={styles.meta}>
        {activeLeague
          ? `Lega: ${activeLeague.name} · Stagione ${entries[0]?.seasonYear ?? "—"}`
          : "Seleziona una lega dal selettore in alto."}
      </Text>

      {loading ? (
        <UiStatePanel
          state="loading"
          title="Caricamento listone"
          message="Recupero calciatori e ruoli…"
          testID="auction-listone-loading"
        />
      ) : null}

      {!loading && loadError ? (
        <View>
          <UiStatePanel
            state="error"
            title="Listone non disponibile"
            message={loadError}
            testID="auction-listone-error"
          />
          <Pressable style={styles.secondaryButton} onPress={onRetry} testID="auction-listone-retry">
            <Text style={styles.secondaryButtonLabel}>Ricarica</Text>
          </Pressable>
        </View>
      ) : null}

      {!loading && !loadError && !activeLeagueId ? (
        <UiStatePanel
          state="empty"
          title="Nessuna lega selezionata"
          message="Scegli una lega per consultare il listone."
          testID="auction-listone-no-league"
        />
      ) : null}

      {!loading && !loadError && activeLeagueId ? (
        <>
          {bidding ? (
            <Text style={styles.meta} testID="auction-listone-bidding-hint">
              L'asta è aperta: scegli il giocatore dall'elenco in «Nuova offerta».
            </Text>
          ) : entries.length === 0 ? (
            <UiStatePanel
              state="empty"
              title="Listone vuoto"
              message="Verrà popolato dagli operatori della piattaforma."
              testID="auction-listone-empty-all"
            />
          ) : (
            <AthleteChooser
              entries={entries}
              ownedAthleteIds={ownedAthleteIds}
              selected={[]}
              onToggle={() => undefined}
              readOnly
              testID="auction-listone-table-all"
            />
          )}
        </>
      ) : null}
    </View>
  );
}
