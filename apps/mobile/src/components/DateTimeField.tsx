import Feather from "@expo/vector-icons/Feather";
import { theme } from "@fantappero/ui/theme";
import { useMemo, useState } from "react";
import { Modal, Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import { lazyStyles } from "../theme/lazyStyles";
import { DISPLAY_FONT } from "../theme/fonts";

const { colors, spacing, radius } = theme;

const MONTHS = ["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio", "agosto", "settembre", "ottobre", "novembre", "dicembre"];
const MONTHS_SHORT = ["gen", "feb", "mar", "apr", "mag", "giu", "lug", "ago", "set", "ott", "nov", "dic"];
const WEEKDAYS = ["L", "M", "M", "G", "V", "S", "D"];
const WEEKDAYS_SHORT = ["dom", "lun", "mar", "mer", "gio", "ven", "sab"];
const HOURS = Array.from({ length: 24 }, (_, i) => i);
const MINUTES = Array.from({ length: 12 }, (_, i) => i * 5);

const pad = (n: number) => String(n).padStart(2, "0");

/** `YYYY-MM-DD HH:MM` (o con la T) → Date locale, o null. */
export function parseDateTimeValue(value: string): Date | null {
  const match = /^(\d{4})-(\d{2})-(\d{2})[ T](\d{2}):(\d{2})/.exec(value.trim());
  if (!match) {
    return null;
  }
  const date = new Date(Number(match[1]), Number(match[2]) - 1, Number(match[3]), Number(match[4]), Number(match[5]));
  return Number.isNaN(date.getTime()) ? null : date;
}

export function formatDateTimeValue(date: Date): string {
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

function formatLabel(date: Date): string {
  return `${WEEKDAYS_SHORT[date.getDay()]} ${date.getDate()} ${MONTHS_SHORT[date.getMonth()]} ${date.getFullYear()} · ${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

/**
 * Campo data e ora: si sceglie da un calendario e da una fascia oraria, senza scrivere a mano.
 * Il valore resta la stringa `AAAA-MM-GG HH:MM` usata dal resto dell'app.
 */
export function DateTimeField({
  label,
  value,
  onChange,
  placeholder = "Scegli data e ora",
  testID,
  min,
  minHint = "Deve essere dopo l'apertura",
}: {
  label?: string;
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  testID?: string;
  /** Valore `AAAA-MM-GG HH:MM` prima del quale non si può scegliere (es. la chiusura dopo l'apertura). */
  min?: string;
  minHint?: string;
}) {
  const minDate = useMemo(() => (min ? parseDateTimeValue(min) : null), [min]);
  const current = useMemo(() => parseDateTimeValue(value), [value]);
  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState<Date>(() => current ?? defaultDraft());
  const [month, setMonth] = useState<Date>(() => new Date((current ?? defaultDraft()).getFullYear(), (current ?? defaultDraft()).getMonth(), 1));

  function openPicker() {
    let base = current ?? defaultDraft();
    if (minDate && base.getTime() <= minDate.getTime()) {
      base = new Date(minDate.getTime() + 60 * 60 * 1000);
    }
    setDraft(base);
    setMonth(new Date(base.getFullYear(), base.getMonth(), 1));
    setOpen(true);
  }

  const days = useMemo(() => {
    const first = new Date(month.getFullYear(), month.getMonth(), 1);
    const offset = (first.getDay() + 6) % 7; // lunedì = 0
    const count = new Date(month.getFullYear(), month.getMonth() + 1, 0).getDate();
    return [...Array.from({ length: offset }, () => 0), ...Array.from({ length: count }, (_, i) => i + 1)];
  }, [month]);

  const today = new Date();
  const isToday = (day: number) =>
    day === today.getDate() && month.getMonth() === today.getMonth() && month.getFullYear() === today.getFullYear();
  const isBeforeMin = (day: number) =>
    !!minDate &&
    new Date(month.getFullYear(), month.getMonth(), day, 23, 59).getTime() <= minDate.getTime();
  const isSelected = (day: number) =>
    day === draft.getDate() && month.getMonth() === draft.getMonth() && month.getFullYear() === draft.getFullYear();

  const invalid = !!minDate && draft.getTime() <= minDate.getTime();

  function pickDay(day: number) {
    setDraft(new Date(month.getFullYear(), month.getMonth(), day, draft.getHours(), draft.getMinutes()));
  }
  function pickTime(hours: number, minutes: number) {
    setDraft(new Date(draft.getFullYear(), draft.getMonth(), draft.getDate(), hours, minutes));
  }

  return (
    <View style={styles.field}>
      {label ? <Text style={styles.label}>{label}</Text> : null}
      <Pressable
        accessibilityRole="button"
        accessibilityLabel={label ? `${label}: ${current ? formatLabel(current) : placeholder}` : placeholder}
        onPress={openPicker}
        style={styles.trigger}
        testID={testID}
      >
        <Feather name="calendar" size={18} color={colors.accent} />
        <Text style={current ? styles.value : styles.placeholder} numberOfLines={1}>
          {current ? formatLabel(current) : placeholder}
        </Text>
      </Pressable>

      <Modal visible={open} transparent animationType="slide" onRequestClose={() => setOpen(false)}>
        <Pressable style={styles.backdrop} onPress={() => setOpen(false)}>
          <Pressable style={styles.sheet} onPress={() => undefined} testID={testID ? `${testID}-sheet` : undefined}>
            <View style={styles.grip} />
            <Text style={styles.sheetTitle}>{label ?? "Data e ora"}</Text>

            <View style={styles.monthRow}>
              <Pressable
                style={styles.arrow}
                accessibilityLabel="Mese precedente"
                onPress={() => setMonth(new Date(month.getFullYear(), month.getMonth() - 1, 1))}
              >
                <Feather name="chevron-left" size={22} color={colors.foreground} />
              </Pressable>
              <Text style={styles.monthLabel}>
                {MONTHS[month.getMonth()]} {month.getFullYear()}
              </Text>
              <Pressable
                style={styles.arrow}
                accessibilityLabel="Mese successivo"
                onPress={() => setMonth(new Date(month.getFullYear(), month.getMonth() + 1, 1))}
              >
                <Feather name="chevron-right" size={22} color={colors.foreground} />
              </Pressable>
            </View>

            <View style={styles.grid}>
              {WEEKDAYS.map((weekday, index) => (
                <Text key={`w${index}`} style={styles.weekday}>
                  {weekday}
                </Text>
              ))}
              {days.map((day, index) =>
                day === 0 ? (
                  <View key={`e${index}`} style={styles.cell} />
                ) : (
                  <Pressable
                    key={`d${day}`}
                    style={[styles.cell, isToday(day) && styles.cellToday, isSelected(day) && styles.cellSelected, isBeforeMin(day) && styles.cellDisabled]}
                    disabled={isBeforeMin(day)}
                    onPress={() => pickDay(day)}
                    accessibilityLabel={`${day} ${MONTHS[month.getMonth()]}`}
                    accessibilityState={{ selected: isSelected(day) }}
                  >
                    <Text style={[styles.cellLabel, isSelected(day) && styles.cellLabelSelected]}>{day}</Text>
                  </Pressable>
                ),
              )}
            </View>

            <Text style={styles.timeTitle}>Ora</Text>
            <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.timeRow}>
              {HOURS.map((hour) => (
                <Pressable
                  key={hour}
                  style={[styles.timeChip, draft.getHours() === hour && styles.timeChipActive]}
                  onPress={() => pickTime(hour, draft.getMinutes())}
                >
                  <Text style={[styles.timeLabel, draft.getHours() === hour && styles.timeLabelActive]}>{pad(hour)}</Text>
                </Pressable>
              ))}
            </ScrollView>
            <Text style={styles.timeTitle}>Minuti</Text>
            <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.timeRow}>
              {MINUTES.map((minute) => (
                <Pressable
                  key={minute}
                  style={[styles.timeChip, draft.getMinutes() === minute && styles.timeChipActive]}
                  onPress={() => pickTime(draft.getHours(), minute)}
                >
                  <Text style={[styles.timeLabel, draft.getMinutes() === minute && styles.timeLabelActive]}>{pad(minute)}</Text>
                </Pressable>
              ))}
            </ScrollView>

            <Text style={styles.summary}>{formatLabel(draft)}</Text>
            {invalid ? <Text style={styles.invalid}>{minHint}</Text> : null}
            <View style={styles.actions}>
              <Pressable style={styles.secondary} onPress={() => setOpen(false)}>
                <Text style={styles.secondaryLabel}>Annulla</Text>
              </Pressable>
              <Pressable
                style={[styles.primary, invalid && { opacity: 0.4 }]}
                disabled={invalid}
                onPress={() => {
                  onChange(formatDateTimeValue(draft));
                  setOpen(false);
                }}
                testID={testID ? `${testID}-confirm` : undefined}
              >
                <Text style={styles.primaryLabel}>Conferma</Text>
              </Pressable>
            </View>
          </Pressable>
        </Pressable>
      </Modal>
    </View>
  );
}

function defaultDraft(): Date {
  const now = new Date();
  now.setMinutes(Math.ceil(now.getMinutes() / 5) * 5, 0, 0);
  return now;
}

const styles = lazyStyles(() =>
  StyleSheet.create({
    field: { gap: spacing.xs },
    label: { color: colors.foregroundMuted, fontSize: 14 },
    trigger: {
      flexDirection: "row",
      alignItems: "center",
      gap: spacing.sm,
      minHeight: 48,
      paddingHorizontal: spacing.md + 4,
      borderRadius: radius.pill,
      borderWidth: 1,
      borderColor: colors.border,
      backgroundColor: colors.background,
    },
    value: { flex: 1, color: colors.foreground, fontWeight: "600" },
    placeholder: { flex: 1, color: colors.foregroundSubtle },
    backdrop: { flex: 1, backgroundColor: "rgba(0,0,0,0.6)", justifyContent: "flex-end" },
    sheet: {
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
    sheetTitle: { color: colors.foreground, fontSize: 26, fontFamily: DISPLAY_FONT, textTransform: "uppercase" },
    monthRow: { flexDirection: "row", alignItems: "center", justifyContent: "space-between" },
    arrow: { width: 40, height: 40, borderRadius: 20, alignItems: "center", justifyContent: "center", backgroundColor: colors.background },
    monthLabel: { color: colors.foreground, fontSize: 18, fontWeight: "700", textTransform: "capitalize" },
    grid: { flexDirection: "row", flexWrap: "wrap" },
    weekday: { width: `${100 / 7}%`, textAlign: "center", color: colors.foregroundMuted, fontSize: 12, paddingVertical: 4 },
    cell: { width: `${100 / 7}%`, aspectRatio: 1, alignItems: "center", justifyContent: "center", borderRadius: 999 },
    cellToday: { borderWidth: 1, borderColor: colors.accent },
    cellDisabled: { opacity: 0.25 },
    invalid: { color: colors.danger, textAlign: "center" },
    cellSelected: { backgroundColor: colors.brand, borderColor: colors.brand },
    cellLabel: { color: colors.foreground, fontWeight: "600" },
    cellLabelSelected: { color: colors.onBrand },
    timeTitle: { color: colors.foregroundMuted, fontSize: 12, letterSpacing: 1.4, textTransform: "uppercase" },
    timeRow: { gap: spacing.xs },
    timeChip: {
      minWidth: 48,
      alignItems: "center",
      paddingVertical: spacing.sm,
      borderRadius: radius.pill,
      borderWidth: 1,
      borderColor: colors.border,
    },
    timeChipActive: { backgroundColor: colors.brand, borderColor: colors.brand },
    timeLabel: { color: colors.foreground, fontWeight: "600" },
    timeLabelActive: { color: colors.onBrand },
    summary: { color: colors.foreground, fontSize: 20, fontFamily: DISPLAY_FONT, textAlign: "center", marginTop: spacing.xs },
    actions: { flexDirection: "row", gap: spacing.sm },
    primary: { flex: 1.4, minHeight: 48, alignItems: "center", justifyContent: "center", borderRadius: radius.pill, backgroundColor: colors.brand },
    primaryLabel: { color: colors.onBrand, fontWeight: "700" },
    secondary: { flex: 1, minHeight: 48, alignItems: "center", justifyContent: "center", borderRadius: radius.pill, borderWidth: 1, borderColor: colors.border },
    secondaryLabel: { color: colors.foreground, fontWeight: "600" },
  }),
);
