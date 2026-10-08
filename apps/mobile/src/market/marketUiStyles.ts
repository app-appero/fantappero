import { lazyStyles } from "../theme/lazyStyles";
import { theme } from "@fantappero/ui/theme";
import { StyleSheet } from "react-native";

const { colors, spacing, typography, radius } = theme;

export const marketUiStyles = lazyStyles(() => StyleSheet.create({
  section: {
    padding: spacing.md,
    borderRadius: radius.md,
    backgroundColor: colors.backgroundElevated,
    gap: spacing.sm,
  },
  sectionTitle: {
    fontSize: typography.fontSize.lg,
    fontWeight: typography.fontWeight.semibold,
    color: colors.foreground,
  },
  rowActions: {
    flexDirection: "row",
    gap: spacing.sm,
    flexWrap: "wrap",
  },
  nominateRow: {
    flexDirection: "row",
    alignItems: "flex-end",
    flexWrap: "wrap",
    gap: spacing.md,
  },
  nominateField: {
    flexGrow: 1,
    flexBasis: 180,
    minWidth: 180,
  },
  lotActions: {
    flexDirection: "row",
    flexWrap: "wrap",
    alignItems: "center",
    gap: spacing.md,
    marginTop: spacing.sm,
  },
  meta: {
    color: colors.foregroundMuted,
    fontSize: typography.fontSize.sm,
  },
  badge: {
    alignSelf: "flex-start",
    paddingHorizontal: spacing.sm,
    paddingVertical: 2,
    borderRadius: radius.sm,
  },
  badgeLabel: {
    fontSize: typography.fontSize.sm,
    fontWeight: typography.fontWeight.semibold,
    color: colors.accentContrast,
  },
  button: {
    minHeight: 44,
    borderRadius: radius.md,
    alignItems: "center",
    justifyContent: "center",
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    backgroundColor: colors.accent,
  },
  buttonLabel: {
    color: colors.accentContrast,
    fontWeight: typography.fontWeight.semibold,
  },
  secondaryButton: {
    minHeight: 44,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.md,
    alignItems: "center",
    justifyContent: "center",
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    backgroundColor: colors.background,
  },
  secondaryButtonLabel: {
    color: colors.foreground,
    fontWeight: typography.fontWeight.semibold,
  },
  disabled: {
    opacity: 0.5,
  },
  input: {
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.md,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    color: colors.foreground,
    backgroundColor: colors.background,
    minHeight: 44,
  },
  fieldLabel: {
    fontSize: typography.fontSize.sm,
    color: colors.foregroundMuted,
  },
  field: {
    gap: spacing.xs,
  },
  error: {
    fontSize: typography.fontSize.sm,
    color: colors.danger,
  },
  success: {
    fontSize: typography.fontSize.sm,
    color: colors.success,
  },
  outcomeList: {
    gap: spacing.xs,
  },
  tableRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingVertical: spacing.sm,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
    gap: spacing.sm,
  },
  tableCell: {
    flex: 1,
    color: colors.foreground,
    fontSize: typography.fontSize.sm,
  },
  chipRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacing.xs,
  },
  chip: {
    minHeight: 40,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    borderRadius: radius.md,
    backgroundColor: colors.backgroundElevated,
    justifyContent: "center",
  },
  chipActive: {
    borderWidth: 1,
    borderColor: colors.accent,
  },
  chipLabel: {
    color: colors.foregroundMuted,
  },
  chipLabelActive: {
    color: colors.foreground,
    fontWeight: typography.fontWeight.semibold,
  },
  optionRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingVertical: spacing.sm,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  optionLabel: {
    color: colors.foreground,
    fontSize: typography.fontSize.sm,
    flex: 1,
  },
  listRow: {
    padding: spacing.md,
    borderRadius: radius.md,
    backgroundColor: colors.backgroundElevated,
    marginBottom: spacing.sm,
    gap: 2,
  },
  nameRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
  },
  roleBadge: {
    minWidth: 28,
    height: 28,
    borderRadius: radius.sm,
    alignItems: "center",
    justifyContent: "center",
    paddingHorizontal: spacing.xs,
  },
  roleBadgeText: {
    fontSize: typography.fontSize.sm,
    fontWeight: typography.fontWeight.semibold,
  },
  name: {
    color: colors.foreground,
    fontWeight: typography.fontWeight.semibold,
    flexShrink: 1,
  },
  override: {
    marginTop: spacing.xs,
    color: colors.warning,
    fontSize: typography.fontSize.sm,
    fontWeight: typography.fontWeight.semibold,
  },
  modalBackdrop: {
    flex: 1,
    backgroundColor: "rgba(0,0,0,0.5)",
    alignItems: "center",
    justifyContent: "center",
    padding: spacing.lg,
  },
  modalCard: {
    width: "100%",
    maxWidth: 420,
    maxHeight: "80%",
    borderRadius: radius.md,
    backgroundColor: colors.backgroundElevated,
    padding: spacing.md,
    gap: spacing.sm,
  },
  gateBar: {
    paddingVertical: spacing.xs,
    paddingHorizontal: spacing.sm,
    borderRadius: radius.md,
    backgroundColor: colors.backgroundElevated,
    gap: spacing.xs,
    marginBottom: spacing.sm,
  },
  gateRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.xs,
    minHeight: 36,
  },
  gateTitle: {
    fontSize: typography.fontSize.sm,
    fontWeight: typography.fontWeight.semibold,
    color: colors.foreground,
  },
  gateStatus: {
    borderRadius: radius.pill,
    borderWidth: 1,
    paddingHorizontal: spacing.sm,
    paddingVertical: 2,
  },
  gateStatusOpen: {
    borderColor: colors.success,
  },
  gateStatusClosed: {
    borderColor: colors.warning,
  },
  gateStatusLabel: {
    fontSize: typography.fontSize.xs,
    fontWeight: typography.fontWeight.semibold,
    color: colors.foreground,
  },
  gateSpacer: {
    flex: 1,
  },
  gateInfo: {
    width: 22,
    height: 22,
    borderRadius: 11,
    borderWidth: 1,
    borderColor: colors.border,
    alignItems: "center",
    justifyContent: "center",
  },
  gateInfoLabel: {
    fontSize: typography.fontSize.sm,
    fontStyle: "italic",
    fontWeight: typography.fontWeight.semibold,
    color: colors.foregroundMuted,
  },
  gateHint: {
    fontSize: typography.fontSize.sm,
    color: colors.foregroundMuted,
  },
}));
