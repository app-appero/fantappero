import { theme } from "@fantappero/ui/theme";
import { useState } from "react";
import { Pressable, ScrollView, StyleSheet, Text, TextInput, View } from "react-native";

const { colors, spacing, typography, radius } = theme;

export type OptionPickerOption = { value: string; label: string };

export type OptionPickerProps = {
  label?: string;
  options: readonly OptionPickerOption[];
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  disabled?: boolean;
  /** Shows an inline search box to filter long option lists (e.g. athlete rosters). */
  searchable?: boolean;
  testID?: string;
};

/**
 * Mobile equivalent of the web `<Select>` — RN has no native dropdown, so this renders
 * a tap-to-expand trigger with an inline option list (same expand/collapse pattern as
 * `BenchOrderPicker` in FormationScreen and the roster admin listone search).
 */
export function OptionPicker({
  label,
  options,
  value,
  onChange,
  placeholder = "Scegli un'opzione…",
  disabled = false,
  searchable = false,
  testID,
}: OptionPickerProps) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const selected = options.find((option) => option.value === value);
  const normalizedQuery = query.trim().toLocaleLowerCase("it-IT");
  const filtered =
    searchable && normalizedQuery
      ? options.filter((option) => option.label.toLocaleLowerCase("it-IT").includes(normalizedQuery))
      : options;

  return (
    <View style={styles.field} testID={testID}>
      {label ? <Text style={styles.label}>{label}</Text> : null}
      <Pressable
        accessibilityRole="button"
        accessibilityState={{ disabled, expanded: open }}
        disabled={disabled}
        onPress={() => setOpen((current) => !current)}
        style={[styles.trigger, disabled ? styles.disabled : null]}
        testID={testID ? `${testID}-trigger` : undefined}
      >
        <Text style={selected ? styles.triggerValue : styles.triggerPlaceholder} numberOfLines={1}>
          {selected ? selected.label : placeholder}
        </Text>
        <Text style={styles.triggerCaret}>{open ? "▲" : "▼"}</Text>
      </Pressable>
      {open && !disabled ? (
        <View style={styles.menu} testID={testID ? `${testID}-menu` : undefined}>
          {searchable ? (
            <TextInput
              style={styles.search}
              value={query}
              onChangeText={setQuery}
              placeholder="Cerca…"
              autoCapitalize="none"
              autoCorrect={false}
              testID={testID ? `${testID}-search` : undefined}
            />
          ) : null}
          <ScrollView style={styles.menuScroll} nestedScrollEnabled keyboardShouldPersistTaps="handled">
            {options.length === 0 ? (
              <Text style={styles.empty}>Nessuna opzione disponibile.</Text>
            ) : filtered.length === 0 ? (
              <Text style={styles.empty}>Nessun risultato per la ricerca.</Text>
            ) : (
              filtered.map((option) => (
                <Pressable
                  key={option.value}
                  style={[styles.option, option.value === value ? styles.optionActive : null]}
                  onPress={() => {
                    onChange(option.value);
                    setOpen(false);
                    setQuery("");
                  }}
                  testID={testID ? `${testID}-option-${option.value}` : undefined}
                >
                  <Text style={styles.optionLabel}>{option.label}</Text>
                </Pressable>
              ))
            )}
          </ScrollView>
        </View>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  field: {
    gap: spacing.xs,
  },
  label: {
    fontSize: typography.fontSize.sm,
    color: colors.foregroundMuted,
  },
  trigger: {
    minHeight: 44,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.md,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    backgroundColor: colors.background,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: spacing.sm,
  },
  disabled: {
    opacity: 0.5,
  },
  triggerValue: {
    color: colors.foreground,
    flexShrink: 1,
  },
  triggerPlaceholder: {
    color: colors.foregroundMuted,
    flexShrink: 1,
  },
  triggerCaret: {
    color: colors.foregroundMuted,
    fontSize: typography.fontSize.sm,
  },
  menu: {
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.md,
    backgroundColor: colors.backgroundElevated,
    marginTop: spacing.xs,
    padding: spacing.xs,
    gap: spacing.xs,
  },
  search: {
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.md,
    paddingHorizontal: spacing.sm,
    paddingVertical: spacing.xs,
    color: colors.foreground,
    backgroundColor: colors.background,
    minHeight: 40,
  },
  menuScroll: {
    maxHeight: 240,
  },
  empty: {
    color: colors.foregroundMuted,
    fontSize: typography.fontSize.sm,
    padding: spacing.sm,
  },
  option: {
    paddingHorizontal: spacing.sm,
    paddingVertical: spacing.sm,
    borderRadius: radius.sm,
  },
  optionActive: {
    backgroundColor: colors.background,
  },
  optionLabel: {
    color: colors.foreground,
    fontSize: typography.fontSize.sm,
  },
});
