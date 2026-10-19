import type {
  FantasyRole,
  FantasyTeam,
  FantasyTeamSummary,
  LeagueListoneEntry,
} from "@fantappero/contracts";
import { useEffect, useState } from "react";
import { Pressable, ScrollView, Text, View } from "react-native";
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
import { SwipeHint, SwipeRow } from "./SwipeRow";
import { rosterStyles as styles } from "./rosterStyles";

function ListoneAssignRow({
  entry,
  owner,
  canAssign,
  canRelease,
  adminBusy,
  onReleaseAthlete,
  onAssignAthlete,
  nudge = false,
}: {
  entry: LeagueListoneEntry;
  owner: AthleteOwnership | undefined;
  canAssign: boolean;
  canRelease: boolean;
  adminBusy: boolean;
  nudge?: boolean;
  onReleaseAthlete: (athleteId: string) => void | Promise<void>;
  onAssignAthlete: (athleteId: string, purchaseCredits: number) => void | Promise<void>;
}) {
  const [draft, setDraft] = useState("1");
  const parsed = Number.parseInt(draft, 10);
  const isValid = Number.isFinite(parsed) && parsed >= 1;
  const roleColors = roleBadgeColors(entry.effectiveRole);

  const assignDisabled = adminBusy || !canAssign || !isValid;
  return (
    <SwipeRow
      onSwipeRight={!owner && !assignDisabled ? () => void onAssignAthlete(entry.athleteId, parsed) : undefined}
      onSwipeLeft={owner && canRelease && !adminBusy ? () => void onReleaseAthlete(entry.athleteId) : undefined}
      rightLabel="Assegna"
      leftLabel="Rimuovi"
      nudge={nudge ? (owner ? "left" : "right") : undefined}
      testID={owner ? `roster-admin-release-${entry.athleteId}` : `roster-admin-assign-${entry.athleteId}`}
    >
      <View style={[styles.playerCard, { marginBottom: 0 }, owner ? { opacity: 0.7 } : null]}>
        <View style={[styles.playerDot, { backgroundColor: roleColors.backgroundColor }]}>
          <Text style={[styles.roleBadgeText, { color: roleColors.color }]}>{entry.effectiveRole}</Text>
        </View>
        <View style={styles.playerBody}>
          <AthleteName athleteId={entry.athleteId} style={styles.playerName} numberOfLines={1} plain>
            {entry.canonicalName}
          </AthleteName>
          <Text style={styles.playerClub} numberOfLines={1}>
            {entry.clubName ?? "—"}
          </Text>
          <View
            style={[
              styles.statusChip,
              { alignSelf: "flex-start", marginTop: 4, backgroundColor: owner ? "rgba(255,255,255,0.1)" : "rgba(52,211,153,0.2)" },
            ]}
            accessibilityLabel={owner ? `In rosa: ${owner.teamName}` : "Libero"}
          >
            <Text style={[styles.statusChipLabel, { color: owner ? "#B9C3E6" : "#6EE7B7" }]} numberOfLines={1}>
              {owner ? `In rosa · ${owner.teamName}` : "Libero"}
            </Text>
          </View>
        </View>
        {!owner ? (
          <View style={{ alignItems: "center", gap: 2 }}>
            <TextInput
              style={styles.priceInputCompact}
              value={draft}
              onChangeText={setDraft}
              keyboardType="numeric"
              editable={!adminBusy && canAssign}
              accessibilityLabel={`Prezzo acquisto ${entry.canonicalName}`}
              testID={`roster-admin-listone-price-${entry.athleteId}`}
            />
            <Text style={styles.playerPriceLabel}>crediti</Text>
          </View>
        ) : null}
      </View>
    </SwipeRow>
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
      <SwipeHint right="scorri a destra per assegnare" left="a sinistra per rimuovere" />
      <View style={styles.playerTable}>
      {pagedRows.map((entry, index) => {
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
            nudge={index === 0 && safePage === 0}
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
  onSelectTargetTeam,
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
  onSelectTargetTeam?: (teamId: string) => void;
  adminMessage: string | null;
  adminError: string | null;
}) {
  const [roleTab, setRoleTab] = useState<RoleTab>("all");
  const [onlyFree, setOnlyFree] = useState(false);
  const ownedAthleteIds = new Set(ownership.keys());

  return (
    <View style={{ gap: 12 }} testID="roster-admin-manual">
      <View style={styles.toolsCard}>
        <Text style={styles.assignHead}>
          Inserimento manuale · assegna a
        </Text>
        {isAdmin && leagueTeams.length > 0 ? (
          <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: 8 }}>
            {leagueTeams.map((row) => {
              const selected = row.id === targetTeam?.id;
              return (
                <Pressable
                  key={row.id}
                  style={[styles.teamPill, selected && styles.pillActive]}
                  disabled={adminBusy}
                  onPress={() => onSelectTargetTeam?.(row.id)}
                >
                  <Text style={[styles.pillLabel, selected && styles.pillLabelActive]} numberOfLines={1}>
                    {row.name}
                  </Text>
                </Pressable>
              );
            })}
          </ScrollView>
        ) : (
          <Text style={styles.subtitle}>
            {isAdmin ? "" : "Assegna o rimuovi calciatori dal listone sulla tua rosa."}
          </Text>
        )}
        {targetTeam ? (
          <Text style={styles.meta} testID="roster-admin-team-summary">
            {targetTeam.name}: {targetTeam.filledSlots}/{targetTeam.rosterSize} slot · {emptySlotsCount} liberi
          </Text>
        ) : null}
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
              <TextInput
                style={styles.searchBox}
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
                <Text style={[styles.meta, { marginLeft: "auto" }]}>{listone.length} calciatori</Text>
              </Pressable>
              <View style={styles.chipRow} accessibilityRole="tablist">
                {ROLE_TABS.map((tab) => {
                  const selected = tab.value === roleTab;
                  return (
                    <Pressable
                      key={tab.value}
                      style={[styles.pill, selected && styles.pillActive]}
                      accessibilityRole="tab"
                      accessibilityState={{ selected }}
                      testID={`roster-admin-listone-tab-${tab.value}`}
                      onPress={() => setRoleTab(tab.value)}
                    >
                      <Text style={[styles.pillLabel, selected && styles.pillLabelActive]}>
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
