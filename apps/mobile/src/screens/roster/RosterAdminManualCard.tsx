import {
  NO_LISTONE_PLACE_FILTERS,
  filterListoneEntries,
  hasListonePlaceFilters,
  listonePlayerCountLabel,
  listoneQuotaNotice,
  normalizeListonePlaceFilters,
  playerAvatarUrl,
  roleQuotaBlockReason,
  rosterRoleQuota,
  sortBySeasonAverageDesc,
} from "@fantappero/contracts";
import type {
  FantasyRole,
  FantasyTeam,
  FantasyTeamSummary,
  LeagueListoneEntry,
  ListonePlaceFilters,
} from "@fantappero/contracts";
import { HScroll } from "../../components/HScroll";
import { PlayerPhotoRing } from "../../components/PlayerPhotoRing";
import { useEffect, useMemo, useState } from "react";
import { AccessibilityInfo, Pressable, ScrollView, Text, View } from "react-native";
import { AppTextInput as TextInput } from "../../components/AppTextInput";
import { AthleteName } from "../../athletes/AthleteCard";
import { UiStatePanel } from "../../components/UiStatePanel";
import { ListoneFilterBar } from "./ListoneFilterBar";
import { foldSearchText } from "./listoneFilter";
import {
  LISTONE_PAGE_SIZE,
  ROLE_LABEL,
  ROLE_TABS,
  roleBadgeColors,
  type AthleteOwnership,
  type RoleTab,
} from "./rosterHelpers";
import { SwipeHint, SwipeRow } from "./SwipeRow";
import { listoneSwipeDecision, roleTabLabel } from "./listoneSwipe";
import { rosterStyles as styles } from "./rosterStyles";
import { AthleteMarketTags } from "../../market/AthleteMarketTags";
import {
  DEFAULT_LISTONE_VIEW_TOGGLES,
  SORT_BY_AVERAGE_LABEL,
  orderListoneRows,
  resetListoneViewToggles,
  type ListoneViewToggles,
} from "../../market/athleteValue";
import { manualAddMinimum, priceCaption, pricePrefill, suggestedDraft } from "../../market/pricePrefill";
import { useSuggestedDraft } from "../../market/useSuggestedDraft";

/** Prezzo dell'aggiunta manuale senza Valore: come oggi, 1 credito. */
const DEFAULT_MANUAL_PRICE = "1";

type AssignAthleteHandler = (
  athleteId: string,
  purchaseCredits: number,
) => void | string | null | Promise<void | string | null>;

function ListoneAssignRow({
  entry,
  owner,
  emptySlotsCount,
  quotaReason,
  canRelease,
  adminBusy,
  onReleaseAthlete,
  onAssignAthlete,
  nudge = false,
  remainingCredits,
  minimumPrice,
}: {
  entry: LeagueListoneEntry;
  owner: AthleteOwnership | undefined;
  emptySlotsCount: number;
  /** Ruolo al completo: il motivo (stesso testo del sito), `null` se il ruolo ha posto. */
  quotaReason: string | null;
  canRelease: boolean;
  adminBusy: boolean;
  nudge?: boolean;
  onReleaseAthlete: (athleteId: string) => void | Promise<void>;
  /** Se restituisce un testo (assegnazione rifiutata), la riga lo mostra sotto di sé. */
  onAssignAthlete: AssignAthleteHandler;
  /** Crediti rimasti della squadra a cui si assegna (`null` se non ancora noti). */
  remainingCredits: number | null;
  /** Partecipante 1, amministratore 0. */
  minimumPrice: number;
}) {
  // Il prezzo parte dal Valore (o dai crediti rimasti se il Valore li supera); senza Valore da 1.
  const prefill = pricePrefill({ marketValue: entry.marketValue, remainingCredits, minimum: minimumPrice });
  const [draft, setDraft] = useSuggestedDraft(suggestedDraft(prefill, DEFAULT_MANUAL_PRICE));
  const parsed = Number.parseInt(draft, 10);
  const isValid = Number.isFinite(parsed) && parsed >= minimumPrice;
  const roleColors = roleBadgeColors(entry.effectiveRole);
  // Motivo di un'assegnazione bloccata o rifiutata, mostrato qui sotto e non solo in cima alla scheda.
  const [rowNotice, setRowNotice] = useState<string | null>(null);
  useEffect(() => {
    if (!quotaReason) {
      setRowNotice(null);
    }
  }, [quotaReason]);
  const showRowNotice = (message: string) => {
    setRowNotice(message);
    AccessibilityInfo.announceForAccessibility(message);
  };

  const decision = listoneSwipeDecision({
    owned: Boolean(owner),
    canRelease,
    busy: adminBusy,
    emptySlotsCount,
    priceValid: isValid,
    quotaReason,
  });
  const canAssign = !owner && emptySlotsCount > 0 && !quotaReason;
  const assign = async () => {
    setRowNotice(null);
    const refusal = await onAssignAthlete(entry.athleteId, parsed);
    if (typeof refusal === "string" && refusal) {
      showRowNotice(refusal);
    }
  };
  const blockedReason = decision.blockedReason;
  return (
    <View>
    <SwipeRow
      onSwipeRight={decision.assign ? () => void assign() : undefined}
      onSwipeLeft={decision.release ? () => void onReleaseAthlete(entry.athleteId) : undefined}
      onBlockedSwipeRight={blockedReason ? () => showRowNotice(blockedReason) : undefined}
      rightLabel="Assegna"
      leftLabel="Rimuovi"
      blockedRightLabel="Pieno"
      nudge={nudge && (owner || decision.assign) ? (owner ? "left" : "right") : undefined}
      testID={owner ? `roster-admin-release-${entry.athleteId}` : `roster-admin-assign-${entry.athleteId}`}
    >
      <View style={[styles.playerCard, { marginBottom: 0 }, owner ? { opacity: 0.7 } : null]}>
        {entry.athleteId ? (
          <PlayerPhotoRing photoUrl={playerAvatarUrl(entry.athleteId, entry.clubName)} role={entry.effectiveRole} size={34} />
        ) : (
          <View style={[styles.playerDot, { backgroundColor: roleColors.backgroundColor }]}>
            <Text style={[styles.roleBadgeText, { color: roleColors.color }]}>{entry.effectiveRole}</Text>
          </View>
        )}
        <View style={styles.playerBody}>
          <AthleteName athleteId={entry.athleteId} style={styles.playerName} numberOfLines={1} plain>
            {entry.canonicalName}
          </AthleteName>
          <Text style={styles.playerClub} numberOfLines={1}>
            {entry.clubName ?? "—"}
          </Text>
          <AthleteMarketTags
            fields={entry}
            style={{ marginTop: 4 }}
            testID={`roster-admin-listone-tags-${entry.athleteId}`}
            leading={
              <View
                style={[
                  styles.statusChip,
                  { maxWidth: "100%", backgroundColor: owner ? "rgba(255,255,255,0.1)" : "rgba(52,211,153,0.2)" },
                ]}
                accessibilityLabel={owner ? `In rosa: ${owner.teamName}` : "Libero"}
              >
                <Text style={[styles.statusChipLabel, { color: owner ? "#B9C3E6" : "#6EE7B7" }]} numberOfLines={1}>
                  {owner ? `In rosa · ${owner.teamName}` : "Libero"}
                </Text>
              </View>
            }
          />
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
            <Text style={styles.playerPriceLabel} testID={`roster-admin-listone-price-caption-${entry.athleteId}`}>
              {priceCaption(draft, prefill)}
            </Text>
          </View>
        ) : null}
      </View>
    </SwipeRow>
    {canAssign && prefill?.note ? (
      <Text style={styles.valueCapNotice} testID={`roster-admin-value-cap-${entry.athleteId}`}>
        {prefill.note}
      </Text>
    ) : null}
    {rowNotice ? (
      <Text
        style={styles.quotaRowNotice}
        accessibilityLiveRegion="polite"
        accessibilityRole="alert"
        testID={`roster-admin-assign-notice-${entry.athleteId}`}
      >
        {rowNotice}
      </Text>
    ) : null}
    </View>
  );
}

function ListoneTable({
  tabValue,
  rows,
  ownership,
  canReleaseAthlete,
  emptySlotsCount,
  quotaReasonByRole,
  adminBusy,
  listoneQuery,
  onlyFree,
  placeKey,
  sortByAverage,
  remainingCredits,
  minimumPrice,
  onReleaseAthlete,
  onAssignAthlete,
}: {
  tabValue: RoleTab;
  rows: readonly LeagueListoneEntry[];
  ownership: Map<string, AthleteOwnership>;
  canReleaseAthlete: (ownerTeamId: string) => boolean;
  emptySlotsCount: number;
  quotaReasonByRole: Record<FantasyRole, string | null>;
  adminBusy: boolean;
  listoneQuery: string;
  onlyFree: boolean;
  /** Campionato e squadra scelti: cambiandoli si torna a pagina 1, come con testo e ruolo. */
  placeKey: string;
  /** «Ordina per media»: cambiando l'ordine si torna a pagina 1. */
  sortByAverage: boolean;
  remainingCredits: number | null;
  minimumPrice: number;
  onReleaseAthlete: (athleteId: string) => void | Promise<void>;
  /** Se restituisce un testo (assegnazione rifiutata), la riga lo mostra sotto di sé. */
  onAssignAthlete: AssignAthleteHandler;
}) {
  const [page, setPage] = useState(0);
  const availabilityKey = listoneQuery.trim() ? "search" : onlyFree ? "free" : "all";
  useEffect(() => {
    setPage(0);
  }, [listoneQuery, tabValue, availabilityKey, placeKey, sortByAverage]);
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
        const canRelease = owner ? canReleaseAthlete(owner.teamId) : false;
        return (
          <ListoneAssignRow
            key={entry.athleteId}
            entry={entry}
            owner={owner}
            emptySlotsCount={emptySlotsCount}
            quotaReason={quotaReasonByRole[entry.effectiveRole] ?? null}
            canRelease={canRelease}
            adminBusy={adminBusy}
            nudge={index === 0 && safePage === 0}
            onReleaseAthlete={onReleaseAthlete}
            onAssignAthlete={onAssignAthlete}
            remainingCredits={remainingCredits}
            minimumPrice={minimumPrice}
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
  ownTeamId = null,
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
  remainingCredits = null,
}: {
  isAdmin: boolean;
  leagueTeams: FantasyTeamSummary[];
  targetTeam: FantasyTeam | null;
  /** Squadra di chi guarda: se l'admin assegna a un'altra, gli avvisi di quota la nominano. */
  ownTeamId?: string | null;
  /**
   * Crediti rimasti della squadra a cui si assegna: il prezzo che parte dal Valore non li
   * supera (Rosario, 21/11). `null` se non ancora noti.
   */
  remainingCredits?: number | null;
  emptySlotsCount: number;
  listone: LeagueListoneEntry[];
  listoneQuery: string;
  onListoneQueryChange: (value: string) => void;
  ownership: Map<string, AthleteOwnership>;
  canReleaseAthlete: (ownerTeamId: string) => boolean;
  adminBusy: boolean;
  onReleaseAthlete: (athleteId: string) => void | Promise<void>;
  /** Se restituisce un testo (assegnazione rifiutata), la riga lo mostra sotto di sé. */
  onAssignAthlete: AssignAthleteHandler;
  onSelectTargetTeam?: (teamId: string) => void;
  adminMessage: string | null;
  adminError: string | null;
}) {
  const [roleTab, setRoleTab] = useState<RoleTab>("all");
  // «Solo disponibili» e «Ordina per media» (1.3, accanto).
  const [toggles, setToggles] = useState<ListoneViewToggles>(DEFAULT_LISTONE_VIEW_TOGGLES);
  const { onlyFree, sortByAverage } = toggles;
  const minimumPrice = manualAddMinimum(isAdmin);
  const [chosenPlace, setChosenPlace] = useState<ListonePlaceFilters>(NO_LISTONE_PLACE_FILTERS);
  // Un listone ricaricato può non avere più il campionato o la squadra scelti: si torna a «tutti».
  const place = useMemo(() => normalizeListonePlaceFilters(listone, chosenPlace), [listone, chosenPlace]);
  const placeKey = `${place.competitionId ?? ""}|${place.clubId ?? ""}`;
  const placeActive = hasListonePlaceFilters(place);
  const ownedAthleteIds = new Set(ownership.keys());
  // Stessa logica del sito (`@fantappero/contracts`), con la ricerca senza accenti dell'app.
  const filteredRows = filterListoneEntries(
    listone,
    {
      role: roleTab,
      query: listoneQuery,
      onlyFree,
      competitionId: place.competitionId,
      clubId: place.clubId,
    },
    { fold: foldSearchText, ownedAthleteIds },
  );
  // «Ordina per media»: dalla media più alta, chi non l'ha in fondo (contracts, come il sito).
  const rows = orderListoneRows(filteredRows, sortByAverage, sortBySeasonAverageDesc);
  // Quota per ruolo della squadra a cui si assegna: stessa regola del server (contracts).
  const quota = useMemo(() => rosterRoleQuota(targetTeam), [targetTeam]);
  const quotaContext = {
    emptySlotsCount,
    teamName: isAdmin && targetTeam && targetTeam.id !== ownTeamId ? targetTeam.name : null,
  };
  const quotaReasonByRole: Record<FantasyRole, string | null> = {
    P: roleQuotaBlockReason(quota, "P", quotaContext),
    D: roleQuotaBlockReason(quota, "D", quotaContext),
    C: roleQuotaBlockReason(quota, "C", quotaContext),
    A: roleQuotaBlockReason(quota, "A", quotaContext),
  };
  const quotaNotice = listoneQuotaNotice(quota, roleTab, quotaContext);

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
              <ListoneFilterBar
                listone={listone}
                place={place}
                onChange={setChosenPlace}
                onResetAll={() => {
                  // «Azzera filtri»: ruolo su «Tutti» e «Ordina per media» spenta;
                  // «Solo disponibili» resta com'è (Rosario, 22/11).
                  setRoleTab("all");
                  setToggles(resetListoneViewToggles);
                }}
              />
              <View style={styles.freeToggle}>
                <View style={styles.listoneToggles}>
                  {/* Le due caselle affiancate; il conto va a capo a destra se non c'è posto. */}
                  <Pressable
                    style={styles.listoneToggle}
                    onPress={() => setToggles((current) => ({ ...current, onlyFree: !current.onlyFree }))}
                    accessibilityRole="checkbox"
                    accessibilityState={{ checked: onlyFree }}
                    testID="roster-listone-only-free"
                  >
                    <View style={[styles.freeBox, onlyFree && styles.freeBoxOn]}>
                      {onlyFree ? <Text style={styles.freeMark}>✓</Text> : null}
                    </View>
                    <Text style={styles.freeLabel}>Solo disponibili</Text>
                  </Pressable>
                  <Pressable
                    style={styles.listoneToggle}
                    onPress={() => setToggles((current) => ({ ...current, sortByAverage: !current.sortByAverage }))}
                    accessibilityRole="checkbox"
                    accessibilityState={{ checked: sortByAverage }}
                    testID="roster-listone-sort-average"
                  >
                    <View style={[styles.freeBox, sortByAverage && styles.freeBoxOn]}>
                      {sortByAverage ? <Text style={styles.freeMark}>✓</Text> : null}
                    </View>
                    <Text style={styles.freeLabel}>{SORT_BY_AVERAGE_LABEL}</Text>
                  </Pressable>
                  <Text style={[styles.meta, { marginLeft: "auto" }]} testID="roster-listone-count">
                    {listonePlayerCountLabel(rows.length)}
                  </Text>
                </View>
              </View>
              <HScroll accessibilityRole="tablist">
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
                        {tab.value === "all" ? tab.label : roleTabLabel(tab.label, quota?.roles[tab.value])}
                      </Text>
                    </Pressable>
                  );
                })}
              </HScroll>
              {quotaNotice ? (
                <View style={[styles.quotaNotice, { marginTop: 8 }]} testID="roster-admin-quota-notice">
                  <Text style={styles.quotaNoticeText} accessibilityLiveRegion="polite">
                    {quotaNotice}
                  </Text>
                </View>
              ) : null}
              {ROLE_TABS.map((tab) => {
                if (tab.value !== roleTab) {
                  return null;
                }
                if (rows.length === 0) {
                  return (
                    <UiStatePanel
                      key={tab.value}
                      state="empty"
                      title="Nessun calciatore"
                      message={
                        listoneQuery.trim()
                          ? "Nessun risultato per la ricerca corrente."
                          : placeActive
                            ? "Nessun calciatore con i filtri scelti."
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
                    quotaReasonByRole={quotaReasonByRole}
                    adminBusy={adminBusy}
                    listoneQuery={listoneQuery}
                    onlyFree={onlyFree}
                    placeKey={placeKey}
                    sortByAverage={sortByAverage}
                    remainingCredits={remainingCredits}
                    minimumPrice={minimumPrice}
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
