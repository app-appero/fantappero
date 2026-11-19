import { lazyStyles } from "../theme/lazyStyles";
import { getActiveColorScheme, theme } from "@fantappero/ui/theme";
import { StyleSheet } from "react-native";
import { DISPLAY_FONT } from "../theme/fonts";

/**
 * Stili condivisi delle schermate di accesso (login, registrazione, verifica email, password,
 * richiesta tester). In un modulo a parte così i componenti di `auth/` li usano senza importare
 * `AuthScreen` (che a sua volta importa loro).
 */

const { colors, spacing, typography, radius } = theme;

/** Corpo delle schermate secondarie di accesso dentro AuthShell (verifica email, password). */
export const authPageStyles = lazyStyles(() => StyleSheet.create({
  form: { gap: spacing.md },
}));

export const authFormStyles = lazyStyles(() => StyleSheet.create({
  googleNote: { textAlign: "center" },
  root: {
    flex: 1,
    backgroundColor: colors.background,
  },
  brand: {
    marginBottom: spacing.md,
  },
  lead: {
    color: colors.foregroundMuted,
    fontSize: typography.fontSize.sm,
    marginBottom: spacing.md,
  },
  label: {
    marginTop: spacing.sm,
    color: colors.foregroundMuted,
    fontSize: typography.fontSize.sm,
    fontWeight: typography.fontWeight.semibold,
  },
  input: {
    marginTop: spacing.xs,
    minHeight: 54,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 18,
    paddingHorizontal: spacing.md + 2,
    color: colors.foreground,
    backgroundColor: colors.background,
  },
  primaryButton: {
    marginTop: spacing.md,
    minHeight: 58,
    paddingVertical: spacing.md,
    borderRadius: 20,
    backgroundColor: colors.brand,
    alignItems: "center",
    justifyContent: "center",
  },
  primaryLabel: {
    color: colors.onBrand,
    fontWeight: typography.fontWeight.semibold,
    fontSize: typography.fontSize.md,
  },
  secondaryButton: {
    marginTop: spacing.sm,
    minHeight: 44,
    paddingVertical: spacing.md,
    borderRadius: radius.pill,
    borderWidth: 1,
    borderColor: colors.border,
    alignItems: "center",
    justifyContent: "center",
  },
  secondaryLabel: {
    color: colors.foreground,
    fontWeight: typography.fontWeight.semibold,
    fontSize: typography.fontSize.md,
  },
  linkRow: {
    marginTop: spacing.md,
    minHeight: 44,
    justifyContent: "center",
  },
  link: {
    color: colors.accent,
    fontWeight: typography.fontWeight.semibold,
    fontSize: typography.fontSize.sm,
  },
  muted: {
    color: colors.foregroundMuted,
    fontSize: typography.fontSize.sm,
  },
  disabled: {
    opacity: 0.6,
  },
  hero: {
    alignItems: "center",
    gap: spacing.sm,
    marginBottom: spacing.md,
  },
  heroTitle: {
    color: colors.foreground,
    fontSize: typography.fontSize.xl,
    fontStyle: "italic",
    fontWeight: "800",
    textTransform: "uppercase",
    textAlign: "center",
  },
  displayTitleLeft: {
    color: colors.foreground,
    fontSize: 46,
    lineHeight: 48,
    fontFamily: DISPLAY_FONT,
    textTransform: "uppercase",
    marginBottom: spacing.md,
  },
  // Tema scuro: i colori chiari dei mockup. Tema chiaro: le varianti scure dello
  // stesso accento, perché l'azzurro chiaro sull'alone azzurro non si leggeva (QA 18/11).
  displayAccent: { color: getActiveColorScheme() === "light" ? colors.accent : "#8CA8FF" },
  googleMain: {
    minHeight: 58,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: spacing.sm,
    borderRadius: 20,
    backgroundColor: "#FFFFFF",
  },
  googleMarkMain: {
    width: 26,
    height: 26,
    borderRadius: 13,
    borderWidth: 1.5,
    borderColor: "#D9DEEC",
    alignItems: "center",
    justifyContent: "center",
  },
  googleMainLabel: { color: "#11162B", fontWeight: "700", fontSize: typography.fontSize.md },
  appleDisabled: {
    minHeight: 58,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: spacing.sm,
    borderRadius: 20,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.backgroundElevated,
    opacity: 0.5,
  },
  appleGlyph: { color: colors.foreground, fontSize: 20 },
  appleLabel: { color: colors.foreground, fontWeight: "700", fontSize: typography.fontSize.md },
  emailButton: {
    minHeight: 54,
    alignItems: "center",
    justifyContent: "center",
    borderRadius: 20,
    borderWidth: 1.5,
    borderColor: "#7A4DFF",
    backgroundColor: "rgba(122,77,255,0.12)",
  },
  emailButtonLabel: { color: colors.accentSecondary, fontWeight: "700", fontSize: typography.fontSize.md },
  // «Continua con email»: secondario rispetto a Google, solo bordo.
  emailToggle: {
    minHeight: 54,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: spacing.sm,
    borderRadius: 20,
    borderWidth: 1.5,
    borderColor: colors.border,
  },
  emailToggleLabel: { color: colors.foreground, fontWeight: "700", fontSize: typography.fontSize.md },
  googleButton: {
    minHeight: 54,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: spacing.sm,
    borderRadius: 20,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.backgroundElevated,
  },
  googleMark: { width: 24, height: 24, borderRadius: 12, backgroundColor: "#fff", alignItems: "center", justifyContent: "center" },
  googleMarkLabel: { color: "#4285F4", fontWeight: "800", fontSize: 14 },
  centerLink: { minHeight: 40, alignItems: "center", justifyContent: "center" },
  linkUnderline: { color: colors.accent, fontSize: typography.fontSize.sm, textDecorationLine: "underline" },
  linkStrong: { color: colors.accent, fontWeight: typography.fontWeight.semibold, textDecorationLine: "underline" },
  stepBadge: {
    paddingHorizontal: spacing.md,
    paddingVertical: 6,
    borderRadius: radius.pill,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.backgroundElevated,
  },
  stepBadgeLabel: { color: colors.foregroundMuted, fontSize: 12, fontWeight: "600" },
  orRow: { flexDirection: "row", alignItems: "center", gap: spacing.sm },
  orLine: { flex: 1, height: 1, backgroundColor: colors.border },
  heroTitleLeft: {
    color: colors.foreground,
    fontSize: typography.fontSize.xl,
    fontStyle: "italic",
    fontWeight: "800",
    textTransform: "uppercase",
    marginBottom: spacing.xs,
  },
  accountRow: {
    marginTop: spacing.sm,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: spacing.md,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.backgroundElevated,
  },
  accountText: {
    flex: 1,
    minWidth: 0,
  },
  accountCaption: {
    color: colors.foregroundMuted,
    fontSize: 11,
    letterSpacing: 1.4,
    textTransform: "uppercase",
  },
  accountEmail: {
    color: colors.foreground,
    fontWeight: typography.fontWeight.semibold,
  },
}));
