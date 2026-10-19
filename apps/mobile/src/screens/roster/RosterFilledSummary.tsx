import type { FantasyRole, FantasyTeam } from "@fantappero/contracts";
import { useEffect, useState } from "react";
import { Pressable, ScrollView, Text, View } from "react-native";
import { AppTextInput as TextInput } from "../../components/AppTextInput";
import {
  compositionStatusLabel,
  ROLE_SECTION_ORDER,
  ROLE_SECTION_TITLE,
  ROSTER_PAGE_SIZE,
  roleBadgeColors,
} from "./rosterHelpers";
import { AthleteName } from "../../athletes/AthleteCard";
import { RosterActionBadge } from "./RosterActionBadge";
import { rosterStyles as styles } from "./rosterStyles";

type RosterSlot = FantasyTeam["slots"][number];

function PurchaseCreditsCell({
  slot,
  canEdit,
  busy,
  compact = false,
  onUpdatePurchaseCredits,
}: {
  slot: RosterSlot;
  canEdit: boolean;
  busy: boolean;
  compact?: boolean;
  onUpdatePurchaseCredits?: (
    slotIndex: number,
    athleteId: string,
    purchaseCredits: number,
  ) => void | Promise<void>;
}) {
  const [draft, setDraft] = useState(String(slot.purchaseCredits ?? 0));

  useEffect(() => {
    setDraft(String(slot.purchaseCredits ?? 0));
  }, [slot.purchaseCredits]);

  if (!canEdit || !slot.athleteId || !onUpdatePurchaseCredits) {
    return <Text style={styles.playerPriceValue}>{slot.purchaseCredits ?? "—"}</Text>;
  }

  const parsed = Number.parseInt(draft, 10);
  const isValid = Number.isFinite(parsed) && parsed >= 0;
  const isDirty = isValid && parsed !== (slot.purchaseCredits ?? 0);
  const athleteId = slot.athleteId;

  return (
    <View style={compact ? styles.priceRowCompact : styles.priceRow}>
      <TextInput
        style={compact ? styles.priceInputCompact : styles.priceInput}
        value={draft}
        onChangeText={setDraft}
        keyboardType="numeric"
        editable={!busy}
        accessibilityLabel={`Prezzo acquisto ${slot.athleteName ?? "calciatore"}`}
        testID={`roster-purchase-credits-${athleteId}`}
      />
      {isDirty ? (
        <Pressable
          style={[styles.ghostButton, busy && styles.disabled]}
          disabled={busy}
          testID={`roster-purchase-credits-save-${athleteId}`}
          onPress={() => void onUpdatePurchaseCredits(slot.slotIndex, athleteId, parsed)}
        >
          <Text style={styles.ghostButtonLabel}>Salva</Text>
        </Pressable>
      ) : null}
    </View>
  );
}

function RosterRoleSection({
  testId,
  title,
  badge,
  slots,
  countLabel,
  canEdit,
  adminBusy,
  onReleaseAthlete,
  onUpdatePurchaseCredits,
}: {
  testId: string;
  title: string;
  badge?: FantasyRole;
  slots: RosterSlot[];
  countLabel: string;
  canEdit: boolean;
  adminBusy: boolean;
  onReleaseAthlete: (athleteId: string) => void | Promise<void>;
  onUpdatePurchaseCredits?: (
    slotIndex: number,
    athleteId: string,
    purchaseCredits: number,
  ) => void | Promise<void>;
}) {
  const [page, setPage] = useState(0);
  const pageCount = Math.max(1, Math.ceil(slots.length / ROSTER_PAGE_SIZE));
  const safePage = Math.min(page, pageCount - 1);
  const pagedSlots = slots.slice(
    safePage * ROSTER_PAGE_SIZE,
    safePage * ROSTER_PAGE_SIZE + ROSTER_PAGE_SIZE,
  );
  const roleColors = badge ? roleBadgeColors(badge) : null;

  return (
    <View style={styles.roleSection} testID={testId}>
      <View style={styles.sectionHead}>
        {badge && roleColors ? (
          <View style={[styles.sectionDot, { backgroundColor: roleColors.backgroundColor }]}>
            <Text style={[styles.roleBadgeText, { color: roleColors.color }]}>{badge}</Text>
          </View>
        ) : null}
        <Text style={styles.sectionTitle2}>{title}</Text>
        <Text style={styles.sectionCount2}>{countLabel}</Text>
      </View>
      {slots.length === 0 ? (
        <View style={styles.dashedRow}>
          <Text style={styles.meta}>Nessun giocatore in questo ruolo.</Text>
        </View>
      ) : (
        <>
          <View testID={`${testId}-cards`}>
            {pagedSlots.map((slot) => {
              const dot = roleBadgeColors(slot.role);
              return (
                <View key={slot.id} style={styles.playerCard}>
                  <View style={[styles.playerDot, { backgroundColor: dot.backgroundColor }]}>
                    <Text style={[styles.roleBadgeText, { color: dot.color }]}>{slot.role ?? "?"}</Text>
                  </View>
                  <View style={styles.playerBody}>
                    <AthleteName
                      athleteId={slot.athleteId}
                      style={styles.playerName}
                      numberOfLines={1}
                      plain
                    >
                      {slot.athleteName ?? "Calciatore"}
                    </AthleteName>
                    <Text style={styles.playerClub} numberOfLines={1}>
                      {slot.clubName ?? "—"} · slot {slot.slotIndex + 1}
                    </Text>
                  </View>
                  <View style={styles.playerPrice}>
                    <PurchaseCreditsCell
                      slot={slot}
                      canEdit={canEdit}
                      busy={adminBusy}
                      compact
                      onUpdatePurchaseCredits={onUpdatePurchaseCredits}
                    />
                    <Text style={styles.playerPriceLabel}>crediti</Text>
                  </View>
                  {canEdit && slot.athleteId ? (
                    <RosterActionBadge
                      action="release"
                      disabled={adminBusy}
                      testID={`roster-admin-release-${slot.athleteId}`}
                      accessibilityLabel={`Rimuovi ${slot.athleteName ?? "calciatore"}`}
                      onPress={() => void onReleaseAthlete(slot.athleteId!)}
                    />
                  ) : null}
                </View>
              );
            })}
          </View>
          {pageCount > 1 ? (
            <View style={styles.pagination} testID={`${testId}-pagination`}>
              <Pressable
                style={[styles.ghostButton, safePage === 0 && styles.disabled]}
                disabled={safePage === 0}
                onPress={() => setPage((current) => Math.max(0, current - 1))}
              >
                <Text style={styles.ghostButtonLabel}>Precedente</Text>
              </Pressable>
              <Text style={styles.meta}>
                Pagina {safePage + 1} di {pageCount}
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
        </>
      )}
    </View>
  );
}

export function RosterFilledSummary({
  viewedTeam,
  filledByRole,
  canEdit,
  adminBusy,
  onReleaseAthlete,
  onUpdatePurchaseCredits,
}: {
  viewedTeam: FantasyTeam;
  filledByRole: Record<FantasyRole | "unknown", RosterSlot[]>;
  canEdit: boolean;
  adminBusy: boolean;
  onReleaseAthlete: (athleteId: string) => void | Promise<void>;
  onUpdatePurchaseCredits?: (
    slotIndex: number,
    athleteId: string,
    purchaseCredits: number,
  ) => void | Promise<void>;
}) {
  const compositionLimits = viewedTeam.composition?.limits;
  const roleLimit = (role: FantasyRole): number | null => {
    if (!compositionLimits) {
      return null;
    }
    if (role === "P") {
      return compositionLimits.goalkeepers;
    }
    if (role === "D") {
      return compositionLimits.defenders;
    }
    if (role === "C") {
      return compositionLimits.midfielders;
    }
    return compositionLimits.forwards;
  };

  const [query, setQuery] = useState("");
  const [roleFilter, setRoleFilter] = useState<"all" | FantasyRole>("all");
  const needle = query.trim().toLocaleLowerCase("it-IT");
  const filterSlots = (slots: RosterSlot[]) =>
    needle
      ? slots.filter((slot) =>
          `${slot.athleteName ?? ""} ${slot.clubName ?? ""}`.toLocaleLowerCase("it-IT").includes(needle),
        )
      : slots;
  const counts = viewedTeam.composition?.counts;
  const filledSlotsList = viewedTeam.slots.filter((slot) => slot.athleteId);
  const totalValue = filledSlotsList.reduce((sum, slot) => sum + (slot.purchaseCredits ?? 0), 0);
  const averageCost =
    filledSlotsList.length > 0
      ? (totalValue / filledSlotsList.length).toLocaleString("it-IT", { maximumFractionDigits: 1 })
      : "—";

  return (
    <View testID="roster-success">
      {viewedTeam.composition ? (
        <View testID="roster-composition" style={styles.compositionBox}>
          <View style={styles.tiles}>
            {ROLE_SECTION_ORDER.map((role) => {
              const have = counts?.[role] ?? 0;
              const need = roleLimit(role) ?? 0;
              const ok = need > 0 && have >= need;
              const dot = roleBadgeColors(role);
              return (
                <View key={role} style={[styles.tile, ok ? styles.tileOk : styles.tileMissing]}>
                  <View style={[styles.playerDot, { backgroundColor: dot.backgroundColor, width: 26, height: 26, borderRadius: 13 }]}>
                    <Text style={[styles.roleBadgeText, { color: dot.color }]}>{role}</Text>
                  </View>
                  <Text style={styles.tileCount}>
                    {have}
                    <Text style={styles.tileNeed}>/{need}</Text>
                  </Text>
                  <View style={styles.tileBar}>
                    <View
                      style={[
                        styles.tileFill,
                        {
                          width: `${Math.min(100, need > 0 ? Math.round((have / need) * 100) : 0)}%` as `${number}%`,
                          backgroundColor: ok ? "#34D399" : "#FFD23F",
                        },
                      ]}
                    />
                  </View>
                </View>
              );
            })}
          </View>
          {viewedTeam.composition.issues.map((issue) => (
            <Text key={`${issue.code}-${issue.message}`} style={styles.errorText}>
              {issue.message}
            </Text>
          ))}
        </View>
      ) : null}
      <View style={styles.statTilesRow} testID="roster-value-tiles">
        <View style={styles.statTile}>
          <Text style={styles.heroLabel}>Valore rosa</Text>
          <Text style={styles.statTileValue}>{totalValue}</Text>
          <Text style={styles.statTileSub}>{viewedTeam.filledSlots} acquisti</Text>
        </View>
        <View style={styles.statTile}>
          <Text style={styles.heroLabel}>Costo medio</Text>
          <Text style={styles.statTileValue}>{averageCost}</Text>
          <Text style={styles.statTileSub}>per calciatore</Text>
        </View>
      </View>
      <TextInput
        style={styles.searchBox}
        value={query}
        onChangeText={setQuery}
        placeholder="Cerca calciatore o club"
        autoCapitalize="none"
        autoCorrect={false}
        testID="roster-search"
      />
      <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.pillRow}>
        {(["all", ...ROLE_SECTION_ORDER] as const).map((value) => (
          <Pressable
            key={value}
            style={[styles.pill, roleFilter === value && styles.pillActive]}
            onPress={() => setRoleFilter(value)}
            testID={`roster-role-filter-${value}`}
          >
            <Text style={[styles.pillLabel, roleFilter === value && styles.pillLabelActive]}>
              {value === "all" ? `Tutti ${viewedTeam.filledSlots}` : `${value} ${filledByRole[value].length}`}
            </Text>
          </Pressable>
        ))}
      </ScrollView>
      <View testID="roster-filled-table" style={styles.roleTables}>
        {ROLE_SECTION_ORDER.filter((role) => roleFilter === "all" || roleFilter === role).map((role) => {
          const slots = filterSlots(filledByRole[role]);
          const limit = roleLimit(role);
          return (
            <RosterRoleSection
              key={role}
              testId={`roster-filled-table-${role}`}
              title={ROLE_SECTION_TITLE[role]}
              badge={role}
              slots={slots}
              countLabel={`${filledByRole[role].length}${limit != null ? `/${limit}` : ""}`}
              canEdit={canEdit}
              adminBusy={adminBusy}
              onReleaseAthlete={onReleaseAthlete}
              onUpdatePurchaseCredits={onUpdatePurchaseCredits}
            />
          );
        })}
        {roleFilter === "all" && filledByRole.unknown.length > 0 ? (
          <RosterRoleSection
            testId="roster-filled-table-unknown"
            title="Senza ruolo"
            slots={filledByRole.unknown}
            countLabel={String(filledByRole.unknown.length)}
            canEdit={canEdit}
            adminBusy={adminBusy}
            onReleaseAthlete={onReleaseAthlete}
            onUpdatePurchaseCredits={onUpdatePurchaseCredits}
          />
        ) : null}
      </View>
    </View>
  );
}
