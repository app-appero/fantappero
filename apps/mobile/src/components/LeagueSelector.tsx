import { DISPLAY_FONT } from "../theme/fonts";
import { lazyStyles } from "../theme/lazyStyles";
import { useState, type ReactNode } from "react";
import { Modal, Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import { AppTextInput as TextInput } from "./AppTextInput";
import Feather from "@expo/vector-icons/Feather";
import { theme } from "@fantappero/ui/theme";

const { colors, spacing, typography, radius } = theme;

export type LeagueOption = {
  value: string;
  label: string;
};

export type LeagueSelectorProps = {
  label: string;
  leagues: readonly LeagueOption[];
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  testID?: string;
  /** Nasconde l'etichetta sopra i chip: in header resta solo il nome della lega. */
  showLabel?: boolean;
  /** Rendered once next to the label, e.g. a lock countdown for the active league. */
  accessory?: ReactNode;
  /** Se presenti, la modale mostra anche «Crea lega» / «Unisciti». */
  onCreatePress?: () => void;
  onJoinPress?: () => void;
};

/** Selettore lega compatto: nome della lega corrente + tasto che apre l'elenco in una modale. */
export function LeagueSelector({
  label,
  leagues,
  value,
  onChange,
  placeholder = "Seleziona lega",
  testID = "league-selector",
  showLabel = true,
  accessory,
  onCreatePress,
  onJoinPress,
}: LeagueSelectorProps) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  if (leagues.length === 0) {
    return null;
  }
  const current = leagues.find((league) => league.value === value);
  const normalized = query.trim().toLocaleLowerCase("it-IT");
  const filtered = normalized
    ? leagues.filter((league) => league.label.toLocaleLowerCase("it-IT").includes(normalized))
    : leagues;

  function close() {
    setOpen(false);
    setQuery("");
  }

  return (
    <View style={styles.wrapper} testID={testID}>
      {showLabel || accessory ? (
        <View style={styles.labelRow}>
          {showLabel ? (
            <Text style={styles.label} accessibilityRole="text">
              {label}
            </Text>
          ) : null}
          {accessory}
        </View>
      ) : null}
      <Pressable
        accessibilityRole="button"
        accessibilityLabel={`${label}: ${current?.label ?? placeholder}. Cambia lega`}
        onPress={() => setOpen(true)}
        style={styles.pill}
        testID={`${testID}-trigger`}
      >
        <Text style={styles.pillLabel} numberOfLines={1}>
          {current?.label ?? placeholder}
        </Text>
        <View style={styles.pillCaret}>
          <Feather name="chevron-down" size={20} color={colors.onBrand} />
        </View>
      </Pressable>

      <Modal visible={open} transparent animationType="slide" onRequestClose={close}>
        <Pressable style={styles.backdrop} onPress={close}>
          <Pressable style={styles.sheet} onPress={() => undefined} testID={`${testID}-modal`}>
            <View style={styles.grip} />
            <View style={styles.sheetHead}>
              <Text style={styles.sheetTitle}>
                Le tue leghe <Text style={styles.sheetCount}>{leagues.length}</Text>
              </Text>
              <Pressable accessibilityRole="button" accessibilityLabel="Chiudi" onPress={close} hitSlop={12}>
                <Text style={styles.sheetClose}>✕</Text>
              </Pressable>
            </View>
            {leagues.length > 5 ? (
              <TextInput
                style={styles.search}
                value={query}
                onChangeText={setQuery}
                placeholder="Cerca lega"
                placeholderTextColor={colors.foregroundSubtle}
                autoCapitalize="none"
                autoCorrect={false}
                testID={`${testID}-search`}
              />
            ) : null}
            <ScrollView style={styles.list} contentContainerStyle={styles.listContent} accessibilityRole="radiogroup">
              {filtered.map((league) => {
                const selected = league.value === value;
                return (
                  <Pressable
                    key={league.value}
                    accessibilityRole="radio"
                    accessibilityState={{ selected }}
                    accessibilityLabel={league.label}
                    onPress={() => {
                      onChange(league.value);
                      close();
                    }}
                    style={[styles.row, selected && styles.rowSelected]}
                    testID={`${testID}-${league.value}`}
                  >
                    <View style={styles.avatar}>
                      <Text style={styles.avatarLabel}>{league.label.slice(0, 2).toUpperCase()}</Text>
                    </View>
                    <Text style={styles.rowLabel} numberOfLines={1}>
                      {league.label}
                    </Text>
                    {selected ? <Text style={styles.check}>✓</Text> : null}
                  </Pressable>
                );
              })}
              {filtered.length === 0 ? <Text style={styles.empty}>Nessuna lega trovata.</Text> : null}
            </ScrollView>
            {onCreatePress || onJoinPress ? (
              <View style={styles.actions}>
                {onCreatePress ? (
                  <Pressable
                    accessibilityRole="button"
                    accessibilityLabel="Crea lega"
                    onPress={() => {
                      close();
                      onCreatePress();
                    }}
                    style={styles.primary}
                    testID="header-create-league-link"
                  >
                    <Text style={styles.primaryLabel}>Crea lega</Text>
                  </Pressable>
                ) : null}
                {onJoinPress ? (
                  <Pressable
                    accessibilityRole="button"
                    accessibilityLabel="Unisciti con codice"
                    onPress={() => {
                      close();
                      onJoinPress();
                    }}
                    style={styles.secondary}
                    testID="header-join-league-link"
                  >
                    <Text style={styles.secondaryLabel}>Unisciti</Text>
                  </Pressable>
                ) : null}
              </View>
            ) : null}
          </Pressable>
        </Pressable>
      </Modal>
    </View>
  );
}

const styles = lazyStyles(() => StyleSheet.create({
  wrapper: {
    flexShrink: 1,
  },
  labelRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
    marginBottom: spacing.xs,
  },
  label: {
    color: colors.foregroundSubtle,
    fontSize: typography.fontSize.xs,
  },
  pill: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.xs,
    minHeight: 40,
    maxWidth: 220,
    paddingLeft: spacing.md,
    paddingRight: 3,
    borderRadius: radius.pill,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.backgroundSubtle,
  },
  pillLabel: {
    flexShrink: 1,
    color: colors.foreground,
    fontWeight: typography.fontWeight.semibold,
  },
  pillCaret: {
    width: 32,
    height: 32,
    borderRadius: 16,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.brand,
  },
  pillCaretLabel: { color: colors.onBrand, fontSize: 18, lineHeight: 22 },
  backdrop: { flex: 1, backgroundColor: "rgba(0,0,0,0.6)", justifyContent: "flex-end" },
  sheet: {
    maxHeight: "85%",
    gap: spacing.sm,
    padding: spacing.md,
    paddingBottom: spacing.lg,
    borderTopLeftRadius: 28,
    borderTopRightRadius: 28,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.backgroundElevated,
  },
  grip: { alignSelf: "center", width: 44, height: 5, borderRadius: 3, backgroundColor: colors.border },
  sheetHead: { flexDirection: "row", alignItems: "center", justifyContent: "space-between" },
  sheetTitle: { color: colors.foreground, fontSize: 28, fontFamily: DISPLAY_FONT, textTransform: "uppercase" },
  sheetCount: { color: colors.accent },
  sheetClose: { color: colors.foregroundMuted, fontSize: 20 },
  search: {
    minHeight: 46,
    paddingHorizontal: spacing.md,
    borderRadius: radius.pill,
    borderWidth: 1,
    borderColor: colors.border,
    color: colors.foreground,
    backgroundColor: colors.background,
  },
  list: { flexGrow: 0 },
  listContent: { gap: spacing.xs },
  row: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
    padding: spacing.sm,
    borderRadius: radius.lg,
    borderWidth: 1,
    borderColor: colors.border,
  },
  rowSelected: { borderColor: colors.brand, backgroundColor: colors.backgroundSubtle },
  avatar: {
    width: 38,
    height: 38,
    borderRadius: 19,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.brand,
  },
  avatarLabel: { color: colors.onBrand, fontWeight: "800", fontStyle: "italic" },
  rowLabel: { flex: 1, color: colors.foreground, fontWeight: typography.fontWeight.semibold },
  check: { color: colors.accent, fontWeight: "800", fontSize: 18 },
  empty: { color: colors.foregroundMuted, textAlign: "center", padding: spacing.md },
  actions: { flexDirection: "row", gap: spacing.sm },
  primary: {
    flex: 1,
    minHeight: 48,
    alignItems: "center",
    justifyContent: "center",
    borderRadius: radius.pill,
    backgroundColor: colors.brand,
  },
  primaryLabel: { color: colors.onBrand, fontWeight: "700" },
  secondary: {
    flex: 1,
    minHeight: 48,
    alignItems: "center",
    justifyContent: "center",
    borderRadius: radius.pill,
    borderWidth: 1,
    borderColor: colors.border,
  },
  secondaryLabel: { color: colors.foreground, fontWeight: "600" },
}));
