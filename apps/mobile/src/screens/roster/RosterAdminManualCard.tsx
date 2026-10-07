import type {
  FantasyRole,
  FantasyTeam,
  FantasyTeamSummary,
  LeagueListoneEntry,
} from "@fantappero/contracts";
import { useEffect, useState } from "react";
import { Pressable, Text, TextInput, View } from "react-native";
import { UiStatePanel } from "../../components/UiStatePanel";
import {
  filterListone,
  LISTONE_PAGE_SIZE,
  ROLE_LABEL,
  ROLE_TABS,
  roleBadgeColors,
  type AthleteOwnership,
  type RoleTab,
} from "./rosterHelpers";
import { rosterStyles as styles } from "./rosterStyles";

function ListoneAssignRow({
  entry,
  owner,
  canAssign,
  canRelease,
  adminBusy,
  onReleaseAthlete,
  onAssignAthlete,
}: {
  entry: LeagueListoneEntry;
  owner: AthleteOwnership | undefined;
  canAssign: boolean;
  canRelease: boolean;
  adminBusy: boolean;
  onReleaseAthlete: (athleteId: string) => void | Promise<void>;
  onAssignAthlete: (athleteId: string, purchaseCredits: number) => void | Promise<void>;
}) {
  const [draft, setDraft] = useState("1");
  const parsed = Number.parseInt(draft, 10);
  const isValid = Number.isFinite(parsed) && parsed >= 1;
  const roleColors = roleBadgeColors(entry.effectiveRole);

  return (
    <View style={styles.card}>
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
      </Text>
      <Text style={owner ? styles.statusOwned : styles.statusFree}>
        {owner ? `In rosa: ${owner.teamName}` : "Libero"}
      </Text>
      <View style={styles.priceRow}>
        <Text style={styles.inlineLabel}>Crediti</Text>
        {!owner ? (
          <TextInput
            style={styles.priceInput}
            value={draft}
            onChangeText={setDraft}
            keyboardType="numeric"
            editable={!adminBusy && canAssign}
            accessibilityLabel={`Prezzo acquisto ${entry.canonicalName}`}
            testID={`roster-admin-listone-price-${entry.athleteId}`}
          />
        ) : (
          <Text style={styles.inlineLabel}>—</Text>
        )}
        {owner && canRelease ? (
          <Pressable
            style={[styles.compactButton, adminBusy && styles.disabled]}
            disabled={adminBusy}
            testID={`roster-admin-release-${entry.athleteId}`}
            onPress={() => void onReleaseAthlete(entry.athleteId)}
          >
            <Text style={styles.buttonLabel}>Rimuovi</Text>
          </Pressable>
        ) : !owner ? (
          <Pressable
            style={[styles.compactButton, (adminBusy || !canAssign || !isValid) && styles.disabled]}
            disabled={adminBusy || !canAssign || !isValid}
            testID={`roster-admin-assign-${entry.athleteId}`}
            onPress={() => void onAssignAthlete(entry.athleteId, parsed)}
          >
            <Text style={styles.buttonLabel}>Assegna</Text>
          </Pressable>
        ) : null}
      </View>
    </View>
  );
}

function ListoneTable({
  tabValue,
  rows,
  ownership,
  canReleaseAthlete,
  emptySlotsCount,
  adminBusy,
  onReleaseAthlete,
  onAssignAthlete,
}: {
  tabValue: RoleTab;
  rows: LeagueListoneEntry[];
  ownership: Map<string, AthleteOwnership>;
  canReleaseAthlete: (ownerTeamId: string) => boolean;
  emptySlotsCount: number;
  adminBusy: boolean;
  onReleaseAthlete: (athleteId: string) => void | Promise<void>;
  onAssignAthlete: (athleteId: string, purchaseCredits: number) => void | Promise<void>;
}) {
  const [page, setPage] = useState(0);
  const rowsKey = rows.map((row) => row.athleteId).join("|");
  useEffect(() => {
    setPage(0);
  }, [rowsKey]);
  const pageCount = Math.max(1, Math.ceil(rows.length / LISTONE_PAGE_SIZE));
  const safePage = Math.min(page, pageCount - 1);
  const pagedRows = rows.slice(
    safePage * LISTONE_PAGE_SIZE,
    safePage * LISTONE_PAGE_SIZE + LISTONE_PAGE_SIZE,
  );

  return (
    <View testID={`roster-admin-listone-table-${tabValue}`}>
      {pagedRows.map((entry) => {
        const owner = ownership.get(entry.athleteId);
        const canAssign = !owner && emptySlotsCount > 0;
        const canRelease = owner ? canReleaseAthlete(owner.teamId) : false;
        return (
          <ListoneAssignRow
            key={entry.athleteId}
            entry={entry}
            owner={owner}
            canAssign={canAssign}
            canRelease={canRelease}
            adminBusy={adminBusy}
            onReleaseAthlete={onReleaseAthlete}
            onAssignAthlete={onAssignAthlete}
          />
        );
      })}
      {pageCount > 1 ? (
        <View style={styles.pagination} testID={`roster-admin-listone-pagination-${tabValue}`}>
          <Pressable
            style={[styles.ghostButton, safePage === 0 && styles.disabled]}
            disabled={safePage === 0}
            onPress={() => setPage((current) => Math.max(0, current - 1))}
          >
            <Text style={styles.ghostButtonLabel}>Precedente</Text>
          </Pressable>
          <Text style={styles.meta}>
            Pagina {safePage + 1} di {pageCount} · {rows.length} calciatori
          </Text>
          <Pressable
            style={[styles.ghostButton, safePage >= pageCount - 1 && styles.disabled]}
            disabled={safePage >= pageCount - 1}
            onPress={() => setPage((current) => Math.min(pageCount - 1, current + 1))}
          >
            <Text style={styles.ghostButtonLabel}>Successiva</Text>
          </Pressable>
        </View>
      ) : null}
    </View>
  );
}

export function RosterAdminManualCard({
  isAdmin,
  leagueTeams,
  targetTeam,
  emptySlotsCount,
  listone,
  listoneQuery,
  onListoneQueryChange,
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
  listone: LeagueListoneEntry[];
  listoneQuery: string;
  onListoneQueryChange: (value: string) => void;
  ownership: Map<string, AthleteOwnership>;
  canReleaseAthlete: (ownerTeamId: string) => boolean;
  adminBusy: boolean;
  onReleaseAthlete: (athleteId: string) => void | Promise<void>;
  onAssignAthlete: (athleteId: string, purchaseCredits: number) => void | Promise<void>;
  adminMessage: string | null;
  adminError: string | null;
}) {
  const [roleTab, setRoleTab] = useState<RoleTab>("all");

  return (
    <View style={styles.adjust} testID="roster-admin-manual">
      <Text style={styles.summary}>Inserimento manuale rose</Text>
      <Text style={styles.subtitle}>
        {isAdmin
          ? "Assegna o rimuovi calciatori dal listone sulla squadra target selezionata sopra."
          : "Assegna o rimuovi calciatori dal listone sulla tua rosa."}
      </Text>
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
              {targetTeam.name}: {targetTeam.filledSlots}/{targetTeam.rosterSize} slot ·{" "}
              {emptySlotsCount} liberi
            </Text>
          ) : null}

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

          {listone.length === 0 ? (
            <UiStatePanel
              state="empty"
              title="Listone vuoto"
              message="Il listone ufficiale non è ancora disponibile. Verrà popolato dagli operatori della piattaforma."
              testID="roster-admin-listone-empty"
            />
          ) : (
            <View>
              <Text style={styles.fieldLabel}>Cerca calciatore</Text>
              <TextInput
                style={styles.input}
                value={listoneQuery}
                onChangeText={onListoneQueryChange}
                placeholder="Nome o club…"
                autoCapitalize="none"
                autoCorrect={false}
                testID="roster-admin-listone-search"
              />
              <View style={styles.chipRow} accessibilityRole="tablist">
                {ROLE_TABS.map((tab) => {
                  const selected = tab.value === roleTab;
                  return (
                    <Pressable
                      key={tab.value}
                      style={[styles.chip, selected && styles.chipSelected]}
                      accessibilityRole="tab"
                      accessibilityState={{ selected }}
                      testID={`roster-admin-listone-tab-${tab.value}`}
                      onPress={() => setRoleTab(tab.value)}
                    >
                      <Text style={[styles.chipLabel, selected && styles.chipLabelSelected]}>
                        {tab.label}
                      </Text>
                    </Pressable>
                  );
                })}
              </View>
              {ROLE_TABS.map((tab) => {
                if (tab.value !== roleTab) {
                  return null;
                }
                const rows = filterListone(listone, tab.value, listoneQuery);
                if (rows.length === 0) {
                  return (
                    <UiStatePanel
                      key={tab.value}
                      state="empty"
                      title="Nessun calciatore"
                      message={
                        listoneQuery.trim()
                          ? "Nessun risultato per la ricerca corrente."
                          : tab.value === "all"
                            ? "Il listone è vuoto."
                            : `Nessun ${ROLE_LABEL[tab.value as FantasyRole].toLowerCase()} nel listone.`
                      }
                      testID={`roster-admin-listone-empty-${tab.value}`}
                    />
                  );
                }
                return (
                  <ListoneTable
                    key={tab.value}
                    tabValue={tab.value}
                    rows={rows}
                    ownership={ownership}
                    canReleaseAthlete={canReleaseAthlete}
                    emptySlotsCount={emptySlotsCount}
                    adminBusy={adminBusy}
                    onReleaseAthlete={onReleaseAthlete}
                    onAssignAthlete={onAssignAthlete}
                  />
                );
              })}
            </View>
          )}
        </>
      )}
    </View>
  );
}
