import { theme } from "@fantappero/ui/theme";
import { StyleSheet } from "react-native";

const { colors, spacing, typography, radius } = theme;

/** Shared styles for the global operator panel screens (mobile port of apps/web admin pages). */
export const adminUiStyles = StyleSheet.create({
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
  meta: {
    color: colors.foregroundMuted,
    fontSize: typography.fontSize.sm,
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
  rowActions: {
    flexDirection: "row",
    gap: spacing.sm,
    flexWrap: "wrap",
  },
  linkCard: {
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.md,
    padding: spacing.md,
    backgroundColor: colors.background,
    gap: 2,
  },
  linkCardTitle: {
    color: colors.foreground,
    fontSize: typography.fontSize.md,
    fontWeight: typography.fontWeight.semibold,
  },
  linkCardHint: {
    color: colors.foregroundMuted,
    fontSize: typography.fontSize.sm,
  },
  listRow: {
    padding: spacing.md,
    borderRadius: radius.md,
    backgroundColor: colors.background,
    borderWidth: 1,
    borderColor: colors.border,
    gap: spacing.xs,
  },
  identityRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: spacing.sm,
  },
  name: {
    color: colors.foreground,
    fontSize: typography.fontSize.md,
    fontWeight: typography.fontWeight.semibold,
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
    backgroundColor: colors.background,
    borderWidth: 1,
    borderColor: colors.border,
    justifyContent: "center",
  },
  chipActive: {
    borderColor: colors.accent,
    backgroundColor: colors.backgroundElevated,
  },
  chipLabel: {
    color: colors.foregroundMuted,
    fontSize: typography.fontSize.sm,
  },
  chipLabelActive: {
    color: colors.foreground,
    fontWeight: typography.fontWeight.semibold,
  },
  tableRow: {
    flexDirection: "row",
    alignItems: "center",
    paddingVertical: spacing.sm,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
    gap: spacing.xs,
  },
  tableHeaderRow: {
    backgroundColor: colors.backgroundElevated,
  },
  tableCell: {
    flex: 1,
    color: colors.foreground,
    fontSize: typography.fontSize.sm,
  },
  tableHeaderCell: {
    fontWeight: typography.fontWeight.semibold,
    color: colors.foregroundMuted,
  },
  confirmBox: {
    borderWidth: 1,
    borderColor: colors.warning,
    borderRadius: radius.md,
    padding: spacing.md,
    gap: spacing.sm,
    backgroundColor: colors.backgroundElevated,
  },
});
