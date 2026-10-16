import type { LineupRole } from "@fantappero/contracts";
import { theme } from "@fantappero/ui/theme";
import { useMemo, useState, type ReactNode } from "react";
import { Modal, Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import { AppTextInput as TextInput } from "../../components/AppTextInput";
import { lazyStyles } from "../../theme/lazyStyles";

const { colors, spacing, typography, radius } = theme;

export const ROLE_NAME: Record<LineupRole, string> = {
  P: "Portiere",
  D: "Difensore",
  C: "Centrocampista",
  A: "Attaccante",
};
const ROLE_SHORT: Record<LineupRole, string> = {
  P: "Portiere",
  D: "Difensore",
  C: "Centrocamp.",
  A: "Attaccante",
};

export function roleRingColor(role: string | null | undefined): string {
  if (role === "P") return colors.success;
  if (role === "D") return colors.warning;
  if (role === "C") return colors.accent;
  if (role === "A") return colors.danger;
  return colors.border;
}

export type PitchSlot = {
  index: number;
  role: LineupRole;
  athleteId: string;
  name: string | null;
  locked: boolean;
  scoreLabel: string | null;
  /** Titolare probabile: anello e nome verdi. */
  probable?: boolean;
};

/** Posizione percentuale di ogni slot: righe P / D / C / A, spaziate in base a quanti ne ha il modulo. */
export function pitchPositions(roles: readonly LineupRole[]): { x: number; y: number }[] {
  const ROW_Y: Record<LineupRole, number> = { A: 14, C: 42, D: 70, P: 91 };
  const byRole: Record<LineupRole, number[]> = { P: [], D: [], C: [], A: [] };
  roles.forEach((role, index) => byRole[role].push(index));
  const result: { x: number; y: number }[] = roles.map(() => ({ x: 50, y: 50 }));
  (Object.keys(byRole) as LineupRole[]).forEach((role) => {
    const list = byRole[role];
    list.forEach((slotIndex, i) => {
      const count = list.length;
      const x = count === 1 ? 50 : 14 + (72 * i) / (count - 1);
      // Le file laterali salgono un poco: il campo non è una griglia rigida.
      const bow = count > 2 ? (i === 0 || i === count - 1 ? -2 : 3) : 0;
      result[slotIndex] = { x, y: ROW_Y[role] + bow };
    });
  });
  return result;
}

export function FormationPitch({
  slots,
  selectedIndex,
  disabled,
  onSlotPress,
}: {
  slots: readonly PitchSlot[];
  selectedIndex: number | null;
  disabled: boolean;
  onSlotPress: (index: number) => void;
}) {
  const positions = pitchPositions(slots.map((slot) => slot.role));
  return (
    <View style={styles.pitch} testID="formation-pitch">
      <View style={styles.pitchFrame} />
      <View style={styles.halfway} />
      <View style={styles.centerCircle} />
      <View style={[styles.box, styles.boxTop]} />
      <View style={[styles.box, styles.boxBottom]} />
      {slots.map((slot) => {
        const pos = positions[slot.index];
        const empty = !slot.athleteId;
        const selected = selectedIndex === slot.index;
        return (
          <Pressable
            key={slot.index}
            accessibilityRole="button"
            accessibilityLabel={
              empty
                ? `Scegli ${ROLE_NAME[slot.role]} ${slot.index + 1}`
                : `${slot.name ?? "Giocatore"}: cambia ${ROLE_NAME[slot.role]}`
            }
            disabled={disabled}
            onPress={() => onSlotPress(slot.index)}
            style={[styles.slot, { left: `${pos?.x ?? 50}%` as `${number}%`, top: `${pos?.y ?? 50}%` as `${number}%` }]}
            testID={`formation-starter-${slot.index}`}
          >
            {empty ? (
              <View style={[styles.emptyCircle, selected ? styles.selectedRing : null]}>
                <Text style={styles.plus}>+</Text>
              </View>
            ) : (
              <View
                style={[
                  styles.circle,
                  { borderColor: roleRingColor(slot.role) },
                  slot.probable ? styles.probableRing : null,
                  selected ? styles.selectedRing : null,
                ]}
              >
                <Text style={styles.initial}>{(slot.name ?? "?").trim().charAt(0).toUpperCase()}</Text>
                {slot.locked ? (
                  <View style={styles.lockDot}>
                    <Text style={styles.lockText}>🔒</Text>
                  </View>
                ) : null}
              </View>
            )}
            <View
              style={[
                styles.label,
                slot.probable ? styles.probableLabel : null,
                empty && selected ? styles.labelSelected : null,
              ]}
            >
              <Text style={styles.labelText} numberOfLines={1}>
                {empty ? ROLE_SHORT[slot.role] : surname(slot.name)}
                {!empty && slot.scoreLabel ? ` · ${slot.scoreLabel}` : ""}
              </Text>
            </View>
          </Pressable>
        );
      })}
    </View>
  );
}

function surname(name: string | null): string {
  if (!name) return "";
  const parts = name.trim().split(/\s+/);
  return parts.length > 1 ? parts.slice(1).join(" ") : name;
}

export type Candidate = {
  athleteId: string;
  name: string;
  role?: LineupRole | null;
  state: "libero" | "titolare" | "panchina" | "bloccato";
  stateLabel: string;
  scoreLabel: string | null;
  current: boolean;
};

type Filter = "tutti" | "libero" | "titolare" | "panchina";
const FILTERS: { id: Filter; label: string }[] = [
  { id: "tutti", label: "Tutti" },
  { id: "libero", label: "Liberi" },
  { id: "titolare", label: "Schierati" },
  { id: "panchina", label: "In panchina" },
];

type RoleFilter = "tutti" | LineupRole;
const ROLE_FILTERS: { id: RoleFilter; label: string; a11y: string }[] = [
  { id: "tutti", label: "Tutti", a11y: "Tutti i ruoli" },
  { id: "P", label: "P", a11y: "Portieri" },
  { id: "D", label: "D", a11y: "Difensori" },
  { id: "C", label: "C", a11y: "Centrocampisti" },
  { id: "A", label: "A", a11y: "Attaccanti" },
];

export function BottomSheet({
  visible,
  title,
  subtitle,
  onClose,
  children,
  badge,
  testID,
}: {
  visible: boolean;
  title: string;
  subtitle?: string;
  onClose: () => void;
  children: ReactNode;
  badge?: ReactNode;
  testID?: string;
}) {
  return (
    <Modal visible={visible} transparent animationType="slide" onRequestClose={onClose}>
      <View style={styles.backdrop}>
        <Pressable style={styles.backdropTap} onPress={onClose} accessibilityLabel="Chiudi" />
        <View style={styles.sheet} testID={testID}>
          <View style={styles.handle} />
          <View style={styles.sheetHeader}>
            {badge}
            <View style={styles.sheetTitleWrap}>
              <Text style={styles.sheetTitle}>{title}</Text>
              {subtitle ? <Text style={styles.sheetSubtitle}>{subtitle}</Text> : null}
            </View>
            <Pressable accessibilityRole="button" accessibilityLabel="Chiudi" onPress={onClose} hitSlop={12}>
              <Text style={styles.close}>✕</Text>
            </Pressable>
          </View>
          {children}
        </View>
      </View>
    </Modal>
  );
}

export function PlayerPickerSheet({
  visible,
  role,
  slotNumber,
  moduleCode,
  candidates,
  hasCurrent,
  onPick,
  onClear,
  onClose,
  title,
  subtitle,
  showRoleTabs = false,
}: {
  visible: boolean;
  role: LineupRole;
  slotNumber: number;
  moduleCode: string;
  candidates: readonly Candidate[];
  hasCurrent: boolean;
  onPick: (athleteId: string) => void;
  onClear: () => void;
  onClose: () => void;
  title?: string;
  subtitle?: string;
  /** Tab P/D/C/A: la panchina mescola i ruoli, gli slot titolari no. */
  showRoleTabs?: boolean;
}) {
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState<Filter>("tutti");
  const [roleFilter, setRoleFilter] = useState<RoleFilter>(showRoleTabs ? role : "tutti");
  const shown = useMemo(() => {
    const q = query.trim().toLowerCase();
    return candidates.filter((c) => {
      if (q && !c.name.toLowerCase().includes(q)) return false;
      if (showRoleTabs && roleFilter !== "tutti" && c.role !== roleFilter) return false;
      if (filter === "tutti") return true;
      if (filter === "libero") return c.state === "libero";
      return c.state === filter;
    });
  }, [candidates, query, filter, roleFilter, showRoleTabs]);
  return (
    <BottomSheet
      visible={visible}
      title={title ?? `Scegli ${ROLE_NAME[role].toLowerCase()}`}
      subtitle={subtitle ?? `Slot ${role} ${slotNumber} · modulo ${moduleCode}`}
      onClose={onClose}
      testID="formation-picker"
      badge={
        <View style={[styles.roleDot, { backgroundColor: roleRingColor(role) }]}>
          <Text style={styles.roleDotText}>{role}</Text>
        </View>
      }
    >
      <TextInput
        value={query}
        onChangeText={setQuery}
        placeholder="Cerca nella rosa"
        autoCorrect={false}
        style={styles.search}
        accessibilityLabel="Cerca nella rosa"
        testID="formation-picker-search"
      />
      {showRoleTabs ? (
        <View style={styles.filters} testID="formation-picker-roles">
          {ROLE_FILTERS.map((tab) => (
            <Pressable
              key={tab.id}
              accessibilityRole="button"
              accessibilityLabel={tab.a11y}
              accessibilityState={{ selected: roleFilter === tab.id }}
              onPress={() => setRoleFilter(tab.id)}
              style={[styles.filter, roleFilter === tab.id ? styles.filterActive : null]}
              testID={`formation-picker-role-${tab.id}`}
            >
              <Text style={styles.filterText}>{tab.label}</Text>
            </Pressable>
          ))}
        </View>
      ) : null}
      <View style={styles.filters}>
        {FILTERS.map((f) => (
          <Pressable
            key={f.id}
            accessibilityRole="button"
            onPress={() => setFilter(f.id)}
            style={[styles.filter, filter === f.id ? styles.filterActive : null]}
          >
            <Text style={styles.filterText}>{f.label}</Text>
          </Pressable>
        ))}
      </View>
      <ScrollView style={styles.list} contentContainerStyle={styles.listContent}>
        {shown.length === 0 ? <Text style={styles.empty}>Nessun calciatore corrisponde.</Text> : null}
        {shown.map((c) => (
          <Pressable
            key={c.athleteId}
            accessibilityRole="button"
            accessibilityLabel={`Schiera ${c.name}`}
            disabled={c.state === "bloccato" && !c.current}
            onPress={() => onPick(c.athleteId)}
            style={[
              styles.cand,
              c.current ? styles.candCurrent : null,
              c.state === "bloccato" && !c.current ? styles.candLocked : null,
            ]}
            testID={`formation-pick-${c.athleteId}`}
          >
            <View style={[styles.roleDotSm, { backgroundColor: roleRingColor(c.role ?? role) }]}>
              <Text style={styles.roleDotText}>{c.role ?? role}</Text>
            </View>
            <View style={styles.candBody}>
              <Text style={styles.candName} numberOfLines={1}>
                {c.name}
              </Text>
              {c.scoreLabel ? <Text style={styles.candMeta}>Punteggio {c.scoreLabel}</Text> : null}
            </View>
            <View style={[styles.stateChip, c.state === "libero" ? styles.stateFree : null, c.state === "bloccato" ? styles.stateLocked : null]}>
              <Text style={styles.stateText}>{c.stateLabel}</Text>
            </View>
          </Pressable>
        ))}
      </ScrollView>
      {hasCurrent ? (
        <Pressable accessibilityRole="button" onPress={onClear} style={styles.clear} testID="formation-picker-clear">
          <Text style={styles.clearText}>Lascia lo slot vuoto</Text>
        </Pressable>
      ) : null}
    </BottomSheet>
  );
}

const styles = lazyStyles(() =>
  StyleSheet.create({
    pitch: {
      height: 470,
      borderRadius: 26,
      overflow: "hidden",
      backgroundColor: "#0f6b4f",
      borderWidth: 1,
      borderColor: "rgba(255,255,255,0.14)",
    },
    pitchFrame: {
      position: "absolute",
      top: 12,
      bottom: 12,
      left: 12,
      right: 12,
      borderWidth: 2,
      borderColor: "rgba(255,255,255,0.32)",
      borderRadius: 10,
    },
    halfway: {
      position: "absolute",
      left: 12,
      right: 12,
      top: "50%",
      height: 2,
      backgroundColor: "rgba(255,255,255,0.32)",
    },
    centerCircle: {
      position: "absolute",
      left: "50%",
      top: "50%",
      width: 84,
      height: 84,
      marginLeft: -42,
      marginTop: -42,
      borderRadius: 42,
      borderWidth: 2,
      borderColor: "rgba(255,255,255,0.32)",
    },
    box: {
      position: "absolute",
      left: "28%",
      right: "28%",
      height: "12%",
      borderWidth: 2,
      borderColor: "rgba(255,255,255,0.32)",
    },
    boxTop: { top: 12, borderTopWidth: 0 },
    boxBottom: { bottom: 12, borderBottomWidth: 0 },
    slot: {
      position: "absolute",
      width: 84,
      marginLeft: -42,
      marginTop: -30,
      alignItems: "center",
      gap: 4,
    },
    circle: {
      width: 46,
      height: 46,
      borderRadius: 23,
      borderWidth: 4,
      backgroundColor: "#ffffff",
      alignItems: "center",
      justifyContent: "center",
    },
    emptyCircle: {
      width: 46,
      height: 46,
      borderRadius: 23,
      borderWidth: 2,
      borderStyle: "dashed",
      borderColor: "rgba(255,255,255,0.8)",
      backgroundColor: "rgba(255,255,255,0.14)",
      alignItems: "center",
      justifyContent: "center",
    },
    selectedRing: {
      borderColor: "#ffffff",
      borderWidth: 4,
    },
    probableRing: {
      borderColor: colors.success,
      borderWidth: 4,
      shadowColor: colors.success,
      shadowOffset: { width: 0, height: 0 },
      shadowOpacity: 1,
      shadowRadius: 8,
      elevation: 6,
    },
    probableLabel: {
      backgroundColor: "#0b8a6b",
    },
    plus: { color: "#ffffff", fontSize: 26, fontWeight: "300", marginTop: -2 },
    initial: { color: "#0A0F22", fontSize: 19, fontStyle: "italic", fontWeight: "800" },
    lockDot: {
      position: "absolute",
      right: -8,
      top: -8,
      width: 20,
      height: 20,
      borderRadius: 10,
      backgroundColor: "#FFD23F",
      alignItems: "center",
      justifyContent: "center",
    },
    lockText: { fontSize: 10 },
    label: {
      maxWidth: 88,
      paddingHorizontal: 8,
      paddingVertical: 2,
      borderRadius: 999,
      backgroundColor: "rgba(8,12,30,0.8)",
    },
    labelSelected: { backgroundColor: colors.brand },
    labelText: { color: "#ffffff", fontSize: 11, fontWeight: "600" },
    backdrop: { flex: 1, backgroundColor: "rgba(5,8,22,0.62)", justifyContent: "flex-end" },
    backdropTap: { flex: 1 },
    sheet: {
      height: "86%",
      maxHeight: "86%",
      overflow: "hidden",
      backgroundColor: colors.backgroundElevated,
      borderTopLeftRadius: 28,
      borderTopRightRadius: 28,
      borderWidth: 1,
      borderColor: colors.border,
      paddingHorizontal: spacing.md,
      paddingTop: spacing.sm,
      paddingBottom: spacing.lg,
      gap: spacing.sm,
    },
    handle: {
      alignSelf: "center",
      width: 44,
      height: 5,
      borderRadius: 999,
      backgroundColor: colors.border,
    },
    sheetHeader: { flexDirection: "row", alignItems: "center", gap: spacing.sm },
    sheetTitleWrap: { flex: 1 },
    sheetTitle: {
      color: colors.foreground,
      fontSize: typography.fontSize.xl,
      fontStyle: "italic",
      fontWeight: "800",
      textTransform: "uppercase",
    },
    sheetSubtitle: { color: colors.foregroundMuted, fontSize: typography.fontSize.sm },
    close: { color: colors.foregroundMuted, fontSize: 20 },
    roleDot: { width: 34, height: 34, borderRadius: 17, alignItems: "center", justifyContent: "center" },
    roleDotSm: { width: 34, height: 34, borderRadius: 17, alignItems: "center", justifyContent: "center" },
    roleDotText: { color: "#11162B", fontWeight: "800", fontStyle: "italic" },
    search: {
      minHeight: 44,
      borderWidth: 1,
      borderColor: colors.border,
      borderRadius: radius.pill,
      paddingHorizontal: spacing.md,
      color: colors.foreground,
    },
    filters: { flexDirection: "row", gap: spacing.xs, flexWrap: "wrap" },
    filter: {
      borderWidth: 1,
      borderColor: colors.border,
      borderRadius: radius.pill,
      paddingHorizontal: spacing.sm,
      paddingVertical: spacing.xs,
    },
    filterActive: { borderColor: colors.brand, borderWidth: 2 },
    filterText: { color: colors.foreground, fontSize: typography.fontSize.sm, fontWeight: "600" },
    list: { flexGrow: 1, flexShrink: 1, flexBasis: 0 },
    listContent: { gap: spacing.xs },
    empty: { color: colors.foregroundMuted, padding: spacing.md },
    cand: {
      flexDirection: "row",
      alignItems: "center",
      gap: spacing.sm,
      padding: spacing.sm,
      borderRadius: radius.lg,
      borderWidth: 1,
      borderColor: colors.border,
    },
    candCurrent: { borderColor: colors.brand, borderWidth: 2 },
    candLocked: { opacity: 0.5 },
    candBody: { flex: 1, minWidth: 0 },
    candName: { color: colors.foreground, fontWeight: "700", fontSize: typography.fontSize.md },
    candMeta: { color: colors.foregroundMuted, fontSize: typography.fontSize.xs },
    stateChip: {
      borderRadius: radius.pill,
      borderWidth: 1,
      borderColor: colors.border,
      paddingHorizontal: spacing.sm,
      paddingVertical: 2,
    },
    stateFree: { borderColor: colors.success },
    stateLocked: { borderColor: colors.warning },
    stateText: { color: colors.foreground, fontSize: typography.fontSize.xs, fontWeight: "600" },
    clear: {
      minHeight: 44,
      alignItems: "center",
      justifyContent: "center",
      borderRadius: radius.pill,
      borderWidth: 1,
      borderColor: colors.border,
    },
    clearText: { color: colors.danger, fontWeight: "600" },
  }),
);
