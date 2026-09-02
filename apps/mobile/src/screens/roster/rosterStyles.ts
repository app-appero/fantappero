import { theme } from "@fantappero/ui/theme";
import { StyleSheet } from "react-native";

const { colors, spacing, typography, radius } = theme;

export const rosterStyles = StyleSheet.create({
  summary: {
    fontSize: typography.fontSize.md,
    color: colors.foreground,
    marginBottom: spacing.sm,
  },
  meta: {
    fontSize: typography.fontSize.sm,
    color: colors.muted,
    marginBottom: spacing.sm,
  },
  compositionBox: {
    marginBottom: spacing.md,
    gap: spacing.xs,
  },
  errorText: {
    fontSize: typography.fontSize.sm,
    color: colors.danger,
  },
  roleTables: {
    gap: spacing.md,
  },
  roleSection: {
    marginBottom: spacing.md,
    gap: spacing.xs,
  },
  roleSectionHeader: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.xs,
    marginBottom: spacing.xs,
  },
  roleSectionTitle: {
    fontSize: typography.fontSize.md,
    fontWeight: typography.fontWeight.semibold,
    color: colors.foreground,
    flex: 1,
  },
  roleSectionCount: {
    fontSize: typography.fontSize.sm,
    color: colors.muted,
  },
  credits: {
    marginBottom: spacing.md,
  },
  inlineAdjust: {
    marginBottom: spacing.sm,
    gap: spacing.xs,
  },
  headerRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: spacing.sm,
    marginBottom: spacing.sm,
  },
  card: {
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.md,
    padding: spacing.md,
    marginBottom: spacing.sm,
    backgroundColor: colors.background,
  },
  cardTitle: {
    fontSize: typography.fontSize.md,
    fontWeight: typography.fontWeight.semibold,
    color: colors.foreground,
    flexShrink: 1,
  },
  row: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
    marginBottom: spacing.xs,
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
  admin: {
    marginTop: spacing.lg,
  },
  adjust: {
    marginTop: spacing.md,
  },
  chipRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacing.xs,
    marginBottom: spacing.sm,
  },
  chip: {
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.md,
    paddingHorizontal: spacing.sm,
    paddingVertical: spacing.xs,
    backgroundColor: colors.background,
  },
  chipSelected: {
    borderColor: colors.accent,
    backgroundColor: colors.accent,
  },
  chipLabel: {
    fontSize: typography.fontSize.sm,
    color: colors.foreground,
  },
  chipLabelSelected: {
    color: colors.accentContrast,
    fontWeight: typography.fontWeight.semibold,
  },
  input: {
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.md,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    marginBottom: spacing.sm,
    color: colors.foreground,
    backgroundColor: colors.background,
    minHeight: 44,
  },
  csvInput: {
    minHeight: 120,
    textAlignVertical: "top",
  },
  button: {
    marginTop: spacing.sm,
    backgroundColor: colors.accent,
    borderRadius: radius.md,
    paddingVertical: spacing.sm,
    paddingHorizontal: spacing.md,
    alignItems: "center",
    minHeight: 44,
    justifyContent: "center",
  },
  disabled: {
    opacity: 0.6,
  },
  buttonLabel: {
    color: colors.accentContrast,
    fontWeight: typography.fontWeight.semibold,
  },
  ok: {
    fontSize: typography.fontSize.sm,
    color: colors.foreground,
    marginTop: spacing.sm,
  },
  error: {
    fontSize: typography.fontSize.sm,
    color: colors.danger,
    marginTop: spacing.sm,
  },
});
