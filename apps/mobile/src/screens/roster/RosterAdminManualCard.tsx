import type {
  FantasyRole,
  FantasyTeam,
  FantasyTeamSummary,
  LeagueListoneEntry,
} from "@fantappero/contracts";
import { useEffect, useState } from "react";
import { Pressable, Text, View } from "react-native";
import { AppTextInput as TextInput } from "../../components/AppTextInput";
import { AthleteName } from "../../athletes/AthleteCard";
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
import { RosterActionBadge } from "./RosterActionBadge";
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
    <View style={styles.playerRow}>
      <View style={[styles.roleBadge, styles.listoneRoleCell, roleColors]}>
        <Text style={[styles.roleBadgeText, { color: roleColors.color }]}>
          {entry.effectiveRole}
        </Text>
      </View>
      <AthleteName
        athleteId={entry.athleteId}
        style={styles.playerName}
        containerStyle={styles.listoneNameCell}
        numberOfLines={1}
      >
        {entry.canonicalName}
      </AthleteName>
      <Text style={[styles.playerClub, styles.listoneClubCell]} numberOfLines={1}>
        {entry.clubName ?? "—"}
      </Text>
      <Text
        style={[
          owner ? styles.listoneStatusOwned : styles.listoneStatusFree,
          styles.listoneStatusCell,
        ]}
        numberOfLines={1}
        accessibilityLabel={owner ? `In rosa: ${owner.teamName}` : "Libero"}
      >
        {owner ? owner.teamName : "Libero"}
      </Text>
      <View style={styles.playerCreditsCell}>
        {!owner ? (
          <TextInput
            style={styles.priceInputCompact}
            value={draft}
            onChangeText={setDraft}
            keyboardType="numeric"
            editable={!adminBusy && canAssign}
            accessibilityLabel={`Prezzo acquisto ${entry.canonicalName}`}
            testID={`roster-admin-listone-price-${entry.athleteId}`}
          />
        ) : (
          <Text style={styles.playerClub}>—</Text>
        )}
      </View>
      {owner && canRelease ? (
        <RosterActionBadge
          action="release"
          disabled={adminBusy}
          testID={`roster-admin-release-${entry.athleteId}`}
          accessibilityLabel={`Rimuovi ${entry.canonicalName}`}
          onPress={() => void onReleaseAthlete(entry.athleteId)}
        />
      ) : !owner ? (
        <RosterActionBadge
          action="assign"
          disabled={adminBusy || !canAssign || !isValid}
          testID={`roster-admin-assign-${entry.athleteId}`}
          accessibilityLabel={`Assegna ${entry.canonicalName}`}
          onPress={() => void onAssignAthlete(entry.athleteId, parsed)}
        />
      ) : (
        <View style={styles.playerActionCell} />
      )}
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
  listoneQuery,
  onlyFree,
  onReleaseAthlete,
  onAssignAthlete,
}: {
  tabValue: RoleTab;
  rows: LeagueListoneEntry[];
  ownership: Map<string, AthleteOwnership>;
  canReleaseAthlete: (ownerTeamId: string) => boolean;
  emptySlotsCount: number;
  adminBusy: boolean;
  listoneQuery: string;
  onlyFree: boolean;
  onReleaseAthlete: (athleteId: string) => void | Promise<void>;
  onAssignAthlete: (athleteId: string, purchaseCredits: number) => void | Promise<void>;
}) {
  const [page, setPage] = useState(0);
  const availabilityKey = listoneQuery.trim() ? "search" : onlyFree ? "free" : "all";
  useEffect(() => {
    setPage(0);
  }, [listoneQuery, tabValue, availabilityKey]);
  const pageCount = Math.max(1, Math.ceil(rows.length / LISTONE_PAGE_SIZE));
  const safePage = Math.min(page, pageCount - 1);
  const pagedRows = rows.slice(
    safePage * LISTONE_PAGE_SIZE,
    safePage * LISTONE_PAGE_SIZE + LISTONE_PAGE_SIZE,
  );

  return (
    <View testID={`roster-admin-listone-table-${tabValue}`}>
      <View style={styles.playerTable}>
        <View style={styles.playerHeaderRow}>
          <Text style={[styles.playerHeaderCell, styles.listoneRoleCell]}> </Text>
          <Text style={[styles.playerHeaderCell, styles.listoneNameCell]}>Calciatore</Text>
          <Text style={[styles.playerHeaderCell, styles.listoneClubCell]}>Club</Text>
          <Text style={[styles.playerHeaderCell, styles.listoneStatusCell]}>Stato</Text>
          <Text style={[styles.playerHeaderCell, styles.playerCreditsCell]}>Crediti</Text>
          <Text style={[styles.playerHeaderCell, styles.playerActionCell]}> </Text>
        </View>
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
      </View>
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
  const [onlyFree, setOnlyFree] = useState(false);
  const ownedAthleteIds = new Set(ownership.keys());

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
              <Pressable
                style={styles.freeToggle}
                onPress={() => setOnlyFree((current) => !current)}
                accessibilityRole="checkbox"
                accessibilityState={{ checked: onlyFree }}
                testID="roster-listone-only-free"
              >
                <View style={[styles.freeBox, onlyFree && styles.freeBoxOn]}>
                  {onlyFree ? <Text style={styles.freeMark}>✓</Text> : null}
                </View>
                <Text style={styles.freeLabel}>Solo disponibili</Text>
              </Pressable>
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
                const rows = filterListone(
                  listone,
                  tab.value,
                  listoneQuery,
                  onlyFree,
                  ownedAthleteIds,
                );
                if (rows.length === 0) {
                  return (
                    <UiStatePanel
                      key={tab.value}
                      state="empty"
                      title="Nessun calciatore"
                      message={
                        listoneQuery.trim()
                          ? "Nessun risultato per la ricerca corrente."
                          : onlyFree
                            ? "Nessun calciatore libero."
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
                    listoneQuery={listoneQuery}
                    onlyFree={onlyFree}
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
