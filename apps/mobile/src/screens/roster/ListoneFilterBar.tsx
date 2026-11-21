import {
  LISTONE_FILTER_ALL_LABEL,
  LISTONE_FILTER_LABEL,
  LISTONE_RESET_FILTERS_LABEL,
  NO_LISTONE_PLACE_FILTERS,
  listoneClubOptions,
  listoneCompetitionOptions,
  listoneFilterChips,
  listoneFilterVisibility,
  removeListoneFilter,
  selectListoneClub,
  selectListoneCompetition,
} from "@fantappero/contracts";
import type { LeagueListoneEntry, ListoneFilterKind, ListonePlaceFilters } from "@fantappero/contracts";
import { theme } from "@fantappero/ui/theme";
import { useMemo, useState } from "react";
import { Modal, Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import { lazyStyles } from "../../theme/lazyStyles";
import {
  listoneSheetRows,
  listoneSheetTitle,
  listoneTriggerAccessibilityLabel,
} from "./listoneFilterSheet";

const { colors, spacing, typography, radius } = theme;

/**
 * «Campionato» e «Squadra» sotto la ricerca del listone (Rosario, 21/11): due menu affiancati
 * che aprono un foglio dal basso (come il selettore della lega), poi i filtri attivi da
 * togliere uno per uno e «Azzera filtri». Con un campionato solo resta solo «Squadra». La
 * logica è in `@fantappero/contracts`, uguale sul web.
 */
export function ListoneFilterBar({
  listone,
  place,
  onChange,
}: {
  listone: readonly LeagueListoneEntry[];
  place: ListonePlaceFilters;
  onChange: (place: ListonePlaceFilters) => void;
}) {
  const [openKind, setOpenKind] = useState<ListoneFilterKind | null>(null);
  const visibility = useMemo(() => listoneFilterVisibility(listone), [listone]);
  const competitionOptions = useMemo(() => listoneCompetitionOptions(listone), [listone]);
  const clubOptions = useMemo(
    () => listoneClubOptions(listone, place.competitionId),
    [listone, place.competitionId],
  );

  if (!visibility.competition && !visibility.club) {
    return null;
  }

  const chips = listoneFilterChips(listone, place);
  const competitionName = competitionOptions.find((option) => option.id === place.competitionId)?.name ?? null;
  const clubName = clubOptions.find((option) => option.id === place.clubId)?.name ?? null;
  const triggers: Array<{ kind: ListoneFilterKind; value: string | null }> = [];
  if (visibility.competition) {
    triggers.push({ kind: "competition", value: competitionName });
  }
  if (visibility.club) {
    triggers.push({ kind: "club", value: clubName });
  }

  const sheetRows =
    openKind === "competition"
      ? listoneSheetRows(competitionOptions, place.competitionId, LISTONE_FILTER_ALL_LABEL.competition)
      : openKind === "club"
        ? listoneSheetRows(clubOptions, place.clubId, LISTONE_FILTER_ALL_LABEL.club)
        : [];
  const sheetTitle =
    openKind === "club"
      ? listoneSheetTitle(LISTONE_FILTER_LABEL.club, competitionName)
      : LISTONE_FILTER_LABEL.competition;

  function close() {
    setOpenKind(null);
  }

  function pick(value: string | null) {
    if (openKind === "competition") {
      onChange(selectListoneCompetition(listone, place, value));
    } else if (openKind === "club") {
      onChange(selectListoneClub(listone, place, value));
    }
    close();
  }

  return (
    <View style={styles.wrapper} testID="roster-listone-filters">
      <View style={styles.triggers}>
        {triggers.map(({ kind, value }) => {
          const valueLabel = value ?? LISTONE_FILTER_ALL_LABEL[kind];
          return (
            <Pressable
              key={kind}
              accessibilityRole="button"
              accessibilityLabel={listoneTriggerAccessibilityLabel(LISTONE_FILTER_LABEL[kind], valueLabel)}
              accessibilityState={{ expanded: openKind === kind }}
              onPress={() => setOpenKind(kind)}
              style={[styles.trigger, value ? styles.triggerActive : null]}
              testID={`roster-listone-${kind}-trigger`}
            >
              <Text style={styles.triggerKind}>{LISTONE_FILTER_LABEL[kind]}</Text>
              <View style={styles.triggerValueRow}>
                <Text style={styles.triggerValue} numberOfLines={1}>
                  {valueLabel}
                </Text>
                <Text style={styles.triggerCaret}>▾</Text>
              </View>
            </Pressable>
          );
        })}
      </View>

      {chips.length > 0 ? (
        <View style={styles.chips} accessibilityLabel="Filtri attivi">
          {chips.map((chip) => (
            <Pressable
              key={chip.kind}
              accessibilityRole="button"
              accessibilityLabel={chip.removeLabel}
              onPress={() => onChange(removeListoneFilter(place, chip.kind))}
              style={styles.chipHit}
              testID={`roster-listone-chip-${chip.kind}`}
            >
              <View style={styles.chip}>
                <Text style={styles.chipLabel} numberOfLines={1}>
                  {chip.label} ×
                </Text>
              </View>
            </Pressable>
          ))}
          <Pressable
            accessibilityRole="button"
            onPress={() => onChange(NO_LISTONE_PLACE_FILTERS)}
            style={styles.reset}
            testID="roster-listone-reset-filters"
          >
            <Text style={styles.resetLabel}>{LISTONE_RESET_FILTERS_LABEL}</Text>
          </Pressable>
        </View>
      ) : null}

      <Modal visible={openKind !== null} transparent animationType="slide" onRequestClose={close}>
        <Pressable style={styles.backdrop} onPress={close} accessibilityLabel="Chiudi">
          <Pressable style={styles.sheet} onPress={() => undefined} testID="roster-listone-filter-sheet">
            <View style={styles.grip} />
            <View style={styles.sheetHead}>
              <Text style={styles.sheetTitle} accessibilityRole="header" numberOfLines={1}>
                {sheetTitle}
              </Text>
              <Pressable
                accessibilityRole="button"
                accessibilityLabel="Chiudi"
                onPress={close}
                style={styles.sheetClose}
                testID="roster-listone-filter-sheet-close"
              >
                <Text style={styles.sheetCloseLabel}>✕</Text>
              </Pressable>
            </View>
            <ScrollView style={styles.list} contentContainerStyle={styles.listContent} accessibilityRole="radiogroup">
              {sheetRows.map((row) => (
                <Pressable
                  key={row.value ?? "all"}
                  accessibilityRole="radio"
                  accessibilityState={{ selected: row.selected }}
                  accessibilityLabel={row.accessibilityLabel}
                  onPress={() => pick(row.value)}
                  style={[styles.row, row.selected ? styles.rowSelected : null]}
                  testID={`roster-listone-filter-option-${row.value ?? "all"}`}
                >
                  <Text style={[styles.rowLabel, row.selected ? styles.rowLabelSelected : null]} numberOfLines={1}>
                    {row.label}
                  </Text>
                  <Text style={styles.rowCount}>{row.count}</Text>
                  {row.selected ? <Text style={styles.rowCheck}>✓</Text> : null}
                </Pressable>
              ))}
            </ScrollView>
          </Pressable>
        </Pressable>
      </Modal>
    </View>
  );
}

const styles = lazyStyles(() => StyleSheet.create({
  wrapper: {
    gap: spacing.xs,
    marginBottom: spacing.xs,
  },
  triggers: {
    flexDirection: "row",
    gap: spacing.sm,
  },
  trigger: {
    flex: 1,
    minWidth: 0,
    minHeight: 48,
    justifyContent: "center",
    gap: 1,
    paddingHorizontal: spacing.md,
    paddingVertical: 6,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.lg,
    backgroundColor: colors.backgroundElevated,
  },
  triggerActive: {
    borderColor: colors.accent,
  },
  triggerKind: {
    fontSize: 10,
    letterSpacing: 0.6,
    textTransform: "uppercase",
    fontWeight: typography.fontWeight.semibold,
    color: colors.foregroundMuted,
  },
  triggerValueRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: spacing.xs,
  },
  triggerValue: {
    flexShrink: 1,
    color: colors.foreground,
    fontSize: typography.fontSize.sm,
    fontWeight: typography.fontWeight.semibold,
  },
  triggerCaret: {
    color: colors.accent,
    fontSize: typography.fontSize.sm,
  },
  chips: {
    flexDirection: "row",
    flexWrap: "wrap",
    alignItems: "center",
    columnGap: spacing.xs,
  },
  chipHit: {
    minHeight: 44,
    justifyContent: "center",
    maxWidth: "100%",
  },
  chip: {
    paddingHorizontal: 10,
    paddingVertical: 3,
    borderRadius: radius.pill,
    borderWidth: 1,
    borderColor: colors.borderStrong,
    backgroundColor: colors.backgroundElevated,
  },
  chipLabel: {
    color: colors.foreground,
    fontSize: 12,
    fontWeight: typography.fontWeight.semibold,
  },
  reset: {
    marginLeft: "auto",
    minHeight: 44,
    justifyContent: "center",
    paddingHorizontal: spacing.xs,
  },
  resetLabel: {
    color: colors.accent,
    fontSize: typography.fontSize.sm,
    fontWeight: typography.fontWeight.semibold,
  },
  backdrop: { flex: 1, backgroundColor: "rgba(0,0,0,0.6)", justifyContent: "flex-end" },
  sheet: {
    maxHeight: "80%",
    gap: spacing.sm,
    padding: spacing.md,
    paddingBottom: spacing.lg,
    borderTopLeftRadius: 24,
    borderTopRightRadius: 24,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.backgroundElevated,
  },
  grip: { alignSelf: "center", width: 44, height: 5, borderRadius: 3, backgroundColor: colors.border },
  sheetHead: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", gap: spacing.sm },
  sheetTitle: {
    flexShrink: 1,
    color: colors.foreground,
    fontSize: typography.fontSize.md,
    fontWeight: typography.fontWeight.semibold,
  },
  sheetClose: { minWidth: 44, minHeight: 44, alignItems: "center", justifyContent: "center" },
  sheetCloseLabel: { color: colors.foregroundMuted, fontSize: 20 },
  list: { flexGrow: 0 },
  listContent: { gap: spacing.xs },
  row: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
    minHeight: 48,
    paddingHorizontal: spacing.sm,
    borderRadius: radius.lg,
    borderWidth: 1,
    borderColor: colors.border,
  },
  rowSelected: { borderColor: colors.brand, backgroundColor: colors.backgroundSubtle },
  rowLabel: { flex: 1, color: colors.foreground, fontWeight: typography.fontWeight.medium },
  rowLabelSelected: { fontWeight: typography.fontWeight.semibold },
  rowCount: { color: colors.foregroundMuted, fontSize: typography.fontSize.sm, fontVariant: ["tabular-nums"] },
  rowCheck: { color: colors.accent, fontWeight: "800", fontSize: 16 },
}));
