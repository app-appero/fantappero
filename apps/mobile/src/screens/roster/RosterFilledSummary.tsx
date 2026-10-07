import type { FantasyRole, FantasyTeam } from "@fantappero/contracts";
import { useEffect, useState } from "react";
import { Pressable, Text, View } from "react-native";
import { AppTextInput as TextInput } from "../../components/AppTextInput";
import {
  compositionStatusLabel,
  ROLE_SECTION_ORDER,
  ROLE_SECTION_TITLE,
  ROSTER_PAGE_SIZE,
  roleBadgeColors,
} from "./rosterHelpers";
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
    return <Text style={styles.meta}>{slot.purchaseCredits ?? "—"}</Text>;
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
      <View style={styles.roleSectionHeader}>
        {badge && roleColors ? (
          <View style={[styles.roleBadge, roleColors]}>
            <Text style={[styles.roleBadgeText, { color: roleColors.color }]}>{badge}</Text>
          </View>
        ) : null}
        <Text style={styles.roleSectionTitle}>{title}</Text>
        <Text style={styles.roleSectionCount}>{countLabel}</Text>
      </View>
      {slots.length === 0 ? (
        <Text style={styles.meta}>Nessun giocatore in questo ruolo.</Text>
      ) : (
        <>
          <View style={styles.playerTable}>
            <View style={styles.playerHeaderRow}>
              <Text style={[styles.playerHeaderCell, styles.playerNameCell]}>Calciatore</Text>
              <Text style={[styles.playerHeaderCell, styles.playerClubCell]}>Club</Text>
              <Text style={[styles.playerHeaderCell, styles.playerCreditsCell]}>Crediti</Text>
              <Text style={[styles.playerHeaderCell, styles.playerSlotCell]}>Slot</Text>
              {canEdit ? <Text style={[styles.playerHeaderCell, styles.playerActionCell]}> </Text> : null}
            </View>
            {pagedSlots.map((slot) => (
              <View key={slot.id} style={styles.playerRow}>
                <Text style={[styles.playerName, styles.playerNameCell]} numberOfLines={1}>
                  {slot.athleteName ?? "Calciatore"}
                </Text>
                <Text style={[styles.playerClub, styles.playerClubCell]} numberOfLines={1}>
                  {slot.clubName ?? "—"}
                </Text>
                <View style={styles.playerCreditsCell}>
                  <PurchaseCreditsCell
                    slot={slot}
                    canEdit={canEdit}
                    busy={adminBusy}
                    compact
                    onUpdatePurchaseCredits={onUpdatePurchaseCredits}
                  />
                </View>
                <Text style={[styles.playerClub, styles.playerSlotCell]}>{slot.slotIndex + 1}</Text>
                {canEdit && slot.athleteId ? (
                  <Pressable
                    style={[styles.rowRemoveButton, adminBusy && styles.disabled]}
                    disabled={adminBusy}
                    testID={`roster-admin-release-${slot.athleteId}`}
                    onPress={() => void onReleaseAthlete(slot.athleteId!)}
                  >
                    <Text style={styles.rowRemoveLabel}>Rimuovi</Text>
                  </Pressable>
                ) : canEdit ? (
                  <View style={styles.playerActionCell} />
                ) : null}
              </View>
            ))}
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

  return (
    <View testID="roster-success">
      <Text style={styles.summary} testID="roster-summary">
        {viewedTeam.name}: {viewedTeam.filledSlots}/{viewedTeam.rosterSize} giocatori
      </Text>
      {viewedTeam.composition ? (
        <View testID="roster-composition" style={styles.compositionBox}>
          <Text style={styles.meta}>
            Composizione: {compositionStatusLabel(viewedTeam.composition.status)}
          </Text>
          <Text style={styles.meta} testID="roster-composition-counts">
            {viewedTeam.composition.counts.P}/{viewedTeam.composition.limits.goalkeepers}P ·{" "}
            {viewedTeam.composition.counts.D}/{viewedTeam.composition.limits.defenders}D ·{" "}
            {viewedTeam.composition.counts.C}/{viewedTeam.composition.limits.midfielders}C ·{" "}
            {viewedTeam.composition.counts.A}/{viewedTeam.composition.limits.forwards}A ·{" "}
            {viewedTeam.composition.competitionCount} campionati
          </Text>
          {viewedTeam.composition.issues.map((issue) => (
            <Text key={`${issue.code}-${issue.message}`} style={styles.errorText}>
              {issue.message}
            </Text>
          ))}
        </View>
      ) : null}
      <View testID="roster-filled-table" style={styles.roleTables}>
        {ROLE_SECTION_ORDER.map((role) => {
          const slots = filledByRole[role];
          const limit = roleLimit(role);
          return (
            <RosterRoleSection
              key={role}
              testId={`roster-filled-table-${role}`}
              title={ROLE_SECTION_TITLE[role]}
              badge={role}
              slots={slots}
              countLabel={`${slots.length}${limit != null ? `/${limit}` : ""}`}
              canEdit={canEdit}
              adminBusy={adminBusy}
              onReleaseAthlete={onReleaseAthlete}
              onUpdatePurchaseCredits={onUpdatePurchaseCredits}
            />
          );
        })}
        {filledByRole.unknown.length > 0 ? (
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
