import type { FantasyTeam, FantasyTeamSummary, LeagueListoneEntry } from "@fantappero/contracts";
import { Pressable, Text, TextInput, View } from "react-native";
import { UiStatePanel } from "../../components/UiStatePanel";
import { ROLE_LABEL, roleBadgeColors, type AthleteOwnership } from "./rosterHelpers";
import { rosterStyles as styles } from "./rosterStyles";

// The listone can hold several hundred players. This screen scrolls inside a
// plain ScrollView (PageContainer), so a virtualized list isn't an option
// here; rendering every row as a native View at once is what was crashing
// the app on real devices (OOM) even though it looked fine in a browser
// preview. Cap the rendered rows and push the user toward the search box
// instead.
const LISTONE_RENDER_LIMIT = 40;

export function RosterAdminManualCard({
  isAdmin,
  leagueTeams,
  targetTeam,
  emptySlotsCount,
  purchaseCredits,
  onPurchaseCreditsChange,
  listone,
  listoneQuery,
  onListoneQueryChange,
  filteredListone,
  ownership,
  canReleaseAthlete,
  adminBusy,
  onReleaseAthlete,
  onAssignAthlete,
  adminMessage,
  adminError,
}: {
  isAdmin: boolean;
  leagueTeams: FantasyTeamSummary[];
  targetTeam: FantasyTeam | null;
  emptySlotsCount: number;
  purchaseCredits: string;
  onPurchaseCreditsChange: (value: string) => void;
  listone: LeagueListoneEntry[];
  listoneQuery: string;
  onListoneQueryChange: (value: string) => void;
  filteredListone: LeagueListoneEntry[];
  ownership: Map<string, AthleteOwnership>;
  canReleaseAthlete: (ownerTeamId: string) => boolean;
  adminBusy: boolean;
  onReleaseAthlete: (athleteId: string) => void | Promise<void>;
  onAssignAthlete: (athleteId: string) => void | Promise<void>;
  adminMessage: string | null;
  adminError: string | null;
}) {
  return (
    <View style={styles.adjust} testID="roster-admin-manual">
      <View style={styles.headerRow}>
        <Text style={styles.summary}>Inserimento manuale rose</Text>
      </View>
      {isAdmin && leagueTeams.length === 0 ? (
        <UiStatePanel
          state="empty"
          title="Nessuna squadra"
          message="Assicura prima le squadre dei partecipanti."
          testID="roster-admin-manual-empty"
        />
      ) : !isAdmin && !targetTeam ? (
        <UiStatePanel
          state="empty"
          title="Nessuna squadra"
          message="La tua rosa non è ancora disponibile."
          testID="roster-admin-manual-empty"
        />
      ) : (
        <>
          {targetTeam ? (
            <Text style={styles.meta} testID="roster-admin-team-summary">
              {targetTeam.name}: {targetTeam.filledSlots}/{targetTeam.rosterSize} ·{" "}
              {emptySlotsCount} liberi
            </Text>
          ) : null}

          <Text style={styles.meta}>Crediti acquisto</Text>
          <TextInput
            style={styles.input}
            value={purchaseCredits}
            onChangeText={onPurchaseCreditsChange}
            keyboardType="numeric"
            testID="roster-purchase-credits"
          />

          {listone.length === 0 ? (
            <UiStatePanel
              state="empty"
              title="Listone vuoto"
              message="Il listone ufficiale non è ancora disponibile. Verrà popolato dagli operatori della piattaforma."
              testID="roster-admin-listone-empty"
            />
          ) : (
            <View testID="roster-admin-listone-table-all">
              <TextInput
                style={styles.input}
                value={listoneQuery}
                onChangeText={onListoneQueryChange}
                placeholder="Cerca per nome o club…"
                autoCapitalize="none"
                autoCorrect={false}
                testID="roster-admin-listone-search"
              />
              {filteredListone.length > LISTONE_RENDER_LIMIT ? (
                <Text style={styles.meta} testID="roster-admin-listone-truncated">
                  Mostrati i primi {LISTONE_RENDER_LIMIT} di {filteredListone.length} risultati.
                  Affina la ricerca per restringere l'elenco.
                </Text>
              ) : null}
              {filteredListone.length === 0 ? (
                <UiStatePanel
                  state="empty"
                  title="Nessun calciatore"
                  message="Nessun risultato per la ricerca corrente."
                  testID="roster-admin-listone-search-empty"
                />
              ) : (
                filteredListone.slice(0, LISTONE_RENDER_LIMIT).map((entry) => {
                  const owner = ownership.get(entry.athleteId);
                  const canAssign = !owner && emptySlotsCount > 0;
                  const canRelease = owner ? canReleaseAthlete(owner.teamId) : false;
                  const roleColors = roleBadgeColors(entry.effectiveRole);
                  return (
                    <View key={entry.athleteId} style={styles.card}>
                      <View style={styles.row}>
                        <View style={[styles.roleBadge, roleColors]}>
                          <Text style={[styles.roleBadgeText, { color: roleColors.color }]}>
                            {entry.effectiveRole}
                          </Text>
                        </View>
                        <Text style={styles.cardTitle}>{entry.canonicalName}</Text>
                      </View>
                      <Text style={styles.meta}>
                        {ROLE_LABEL[entry.effectiveRole]}
                        {entry.clubName ? ` · ${entry.clubName}` : ""}
                        {owner ? ` · In rosa: ${owner.teamName}` : " · Libero"}
                      </Text>
                      {owner && canRelease ? (
                        <Pressable
                          style={[styles.button, adminBusy && styles.disabled]}
                          disabled={adminBusy}
                          testID={`roster-admin-release-${entry.athleteId}`}
                          onPress={() => void onReleaseAthlete(entry.athleteId)}
                        >
                          <Text style={styles.buttonLabel}>Rimuovi</Text>
                        </Pressable>
                      ) : !owner ? (
                        <Pressable
                          style={[styles.button, (adminBusy || !canAssign) && styles.disabled]}
                          disabled={adminBusy || !canAssign}
                          testID={`roster-admin-assign-${entry.athleteId}`}
                          onPress={() => void onAssignAthlete(entry.athleteId)}
                        >
                          <Text style={styles.buttonLabel}>Assegna</Text>
                        </Pressable>
                      ) : null}
                    </View>
                  );
                })
              )}
            </View>
          )}

          {adminMessage ? (
            <Text style={styles.ok} testID="roster-admin-ok">
              {adminMessage}
            </Text>
          ) : null}
          {adminError ? (
            <Text style={styles.error} testID="roster-admin-assign-error">
              {adminError}
            </Text>
          ) : null}
        </>
      )}
    </View>
  );
}
