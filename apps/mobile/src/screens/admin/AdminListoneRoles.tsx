import {
  type AdminListoneProviderRolesResult,
  type AdminListoneRoleRestoreResult,
  type FantasyRole,
  type ListoneRefreshMode,
  DEFAULT_RESTORE_BEFORE,
  LISTONE_REFRESH_CANCEL_LABEL,
  LISTONE_REFRESH_OPTIONS,
  LISTONE_REFRESH_QUESTION,
  LISTONE_REFRESH_ROLES_WARNING,
  LISTONE_REFRESH_TITLE,
  LISTONE_RESTORE_APPLY_LABEL,
  LISTONE_RESTORE_BEFORE_LABEL,
  LISTONE_RESTORE_CONFIRM_NO_LABEL,
  LISTONE_RESTORE_CONFIRM_YES_LABEL,
  LISTONE_RESTORE_INTRO,
  LISTONE_RESTORE_INVALID_INPUT,
  LISTONE_RESTORE_PREVIEW_LABEL,
  LISTONE_RESTORE_TITLE,
  LISTONE_ROLE_PREVIEW_CANCEL_LABEL,
  LISTONE_ROLE_PREVIEW_CONFIRM_LABEL,
  LISTONE_ROLE_PREVIEW_ERROR_FALLBACK,
  LISTONE_ROLE_PREVIEW_ERROR_TITLE,
  LISTONE_ROLE_PREVIEW_INTRO,
  LISTONE_ROLE_PREVIEW_TITLE,
  listoneRefreshStartLabel,
  listoneRestoreConfirmText,
  listoneRestoreDoneMessage,
  listoneRestoreEmptyMessage,
  listoneRestoreSummary,
  listoneRoleChangesSummary,
  romeLocalToIso,
} from "@fantappero/contracts";
import { theme } from "@fantappero/ui/theme";
import { useState } from "react";
import { Modal, Pressable, StyleSheet, Text, View } from "react-native";
import { adminUiStyles as styles } from "../../admin/adminUiStyles";
import { restoreAdminListoneRoles, updateAdminListoneRolesFromProvider } from "../../api/admin";
import { DateTimeField } from "../../components/DateTimeField";
import { UiStatePanel } from "../../components/UiStatePanel";
import { getApiErrorMessage } from "../../session/DemoSessionContext";
import { lazyStyles } from "../../theme/lazyStyles";

const { colors, spacing, typography, radius } = theme;

/**
 * Pannello operatore → Listone, porting di `ListoneProviderRolesPreview`,
 * `ListoneRoleRestoreSection` e della finestra di scelta di `AdminListonePage` (sito dal 22/11,
 * app dalla 1.5). I testi arrivano da `@fantappero/contracts`, gli stessi del sito.
 */

function RoleChip({ role, warn = false }: { role: FantasyRole | null; warn?: boolean }) {
  return (
    <Text style={[local.roleChip, warn && local.roleChipWarn]}>
      {role ?? "non ricostruibile"}
    </Text>
  );
}

/**
 * Finestra «Aggiorna listone dal provider»: prima si sceglie cosa aggiornare, solo dopo parte
 * l'aggiornamento; «Annulla» (o il tasto indietro) chiude senza avviare nulla.
 */
export function ListoneRefreshChoiceModal({
  visible,
  mode,
  onModeChange,
  onCancel,
  onStart,
}: {
  visible: boolean;
  mode: ListoneRefreshMode;
  onModeChange: (mode: ListoneRefreshMode) => void;
  onCancel: () => void;
  onStart: (mode: ListoneRefreshMode) => void;
}) {
  if (!visible) {
    return null;
  }
  return (
    <Modal transparent animationType="fade" visible onRequestClose={onCancel}>
      <View style={styles.confirmOverlay}>
        <View style={styles.confirmBox} testID="admin-listone-refresh-modal">
          <Text style={styles.sectionTitle} accessibilityRole="header">
            {LISTONE_REFRESH_TITLE}
          </Text>
          <View accessibilityRole="radiogroup" testID="admin-listone-refresh-choice">
            <Text style={styles.meta}>{LISTONE_REFRESH_QUESTION}</Text>
            {LISTONE_REFRESH_OPTIONS.map((option) => {
              const checked = mode === option.mode;
              return (
                <Pressable
                  key={option.mode}
                  accessibilityRole="radio"
                  accessibilityState={{ checked }}
                  onPress={() => onModeChange(option.mode)}
                  style={[local.option, checked && local.optionOn]}
                  testID={
                    option.mode === "keep_roles"
                      ? "admin-listone-refresh-mode-keep"
                      : "admin-listone-refresh-mode-roles"
                  }
                >
                  <View style={[local.radio, checked && local.radioOn]}>
                    {checked ? <View style={local.radioDot} /> : null}
                  </View>
                  <View style={local.optionText}>
                    <Text style={local.optionTitle}>{option.title}</Text>
                    <Text style={styles.meta}>{option.hint}</Text>
                  </View>
                </Pressable>
              );
            })}
          </View>
          {mode === "update_roles" ? (
            <Text style={local.warning} testID="admin-listone-refresh-roles-warning">
              {LISTONE_REFRESH_ROLES_WARNING}
            </Text>
          ) : null}
          <View style={styles.rowActions}>
            <Pressable
              style={styles.secondaryButton}
              onPress={onCancel}
              testID="admin-listone-refresh-cancel"
            >
              <Text style={styles.secondaryButtonLabel}>{LISTONE_REFRESH_CANCEL_LABEL}</Text>
            </Pressable>
            <Pressable
              style={styles.button}
              onPress={() => onStart(mode)}
              testID="admin-listone-refresh-start"
            >
              <Text style={styles.buttonLabel}>{listoneRefreshStartLabel(mode)}</Text>
            </Pressable>
          </View>
        </View>
      </View>
    </Modal>
  );
}

/**
 * Anteprima di «Aggiorna anche i ruoli dal fornitore»: chi cambierebbe ruolo, dove è in rosa e
 * quante rose andrebbero fuori quota. I ruoli cambiano solo con «Conferma i nuovi ruoli».
 */
export function ListoneRolePreviewCard({
  preview,
  accessToken,
  onDone,
}: {
  preview: AdminListoneProviderRolesResult;
  accessToken: string | null;
  /** Dopo la conferma (ruoli applicati) o l'annullamento (`null`). */
  onDone: (applied: AdminListoneProviderRolesResult | null) => void;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function confirm() {
    if (!accessToken) {
      setError("Sessione non disponibile. Accedi di nuovo.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const applied = await updateAdminListoneRolesFromProvider(accessToken, {
        seasonYear: preview.seasonYear,
        dryRun: false,
        athleteIds: preview.entries.map((entry) => entry.athleteId),
      });
      onDone(applied);
    } catch (confirmError) {
      setError(getApiErrorMessage(confirmError, LISTONE_ROLE_PREVIEW_ERROR_FALLBACK));
    } finally {
      setBusy(false);
    }
  }

  return (
    <View style={styles.section} testID="admin-listone-role-preview">
      <Text style={styles.sectionTitle}>{LISTONE_ROLE_PREVIEW_TITLE}</Text>
      <Text style={styles.meta} testID="admin-listone-role-preview-summary">
        {listoneRoleChangesSummary(preview.counts)}
      </Text>
      <Text style={styles.meta}>{LISTONE_ROLE_PREVIEW_INTRO}</Text>
      {preview.entries.map((entry) => (
        <View
          key={entry.athleteId}
          style={styles.listRow}
          testID={`admin-listone-role-preview-row-${entry.athleteId}`}
        >
          <Text style={styles.name}>{entry.name}</Text>
          <Text style={styles.meta}>Club: {entry.club ?? "—"}</Text>
          <View style={local.roles}>
            <Text style={styles.meta}>Ruolo ora</Text>
            <RoleChip role={entry.currentRole} />
            <Text style={styles.meta}>Nuovo ruolo</Text>
            <RoleChip role={entry.newRole} warn />
          </View>
          <Text style={styles.meta}>
            In rosa nelle leghe: {entry.inRosters.length > 0 ? entry.inRosters.join(", ") : "—"}
          </Text>
        </View>
      ))}
      {error ? (
        <UiStatePanel
          state="error"
          title={LISTONE_ROLE_PREVIEW_ERROR_TITLE}
          message={error}
          testID="admin-listone-role-preview-error"
        />
      ) : null}
      <Pressable
        style={[local.dangerButton, busy && styles.disabled]}
        disabled={busy}
        onPress={() => void confirm()}
        testID="admin-listone-role-preview-confirm"
      >
        <Text style={local.dangerLabel}>{LISTONE_ROLE_PREVIEW_CONFIRM_LABEL}</Text>
      </Pressable>
      <Pressable
        style={[styles.secondaryButton, busy && styles.disabled]}
        disabled={busy}
        onPress={() => onDone(null)}
        testID="admin-listone-role-preview-cancel"
      >
        <Text style={styles.secondaryButtonLabel}>{LISTONE_ROLE_PREVIEW_CANCEL_LABEL}</Text>
      </Pressable>
    </View>
  );
}

/**
 * «Ripristina i ruoli cambiati da un aggiornamento»: riporta i ruoli a prima di un'ora scelta
 * (ora di Roma). Prima si guarda cosa cambia, poi si conferma.
 */
export function ListoneRoleRestoreCard({
  seasonYear,
  accessToken,
  onRestored,
}: {
  seasonYear: number | null;
  accessToken: string | null;
  /** Dopo un ripristino riuscito (per ricaricare il listone). */
  onRestored?: () => void;
}) {
  // Il campo data usa «AAAA-MM-GG HH:MM»; l'ora si legge sempre come ora di Roma.
  const [before, setBefore] = useState(DEFAULT_RESTORE_BEFORE.replace("T", " "));
  const [preview, setPreview] = useState<AdminListoneRoleRestoreResult | null>(null);
  const [busy, setBusy] = useState<"preview" | "apply" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [confirming, setConfirming] = useState(false);
  const [done, setDone] = useState<AdminListoneRoleRestoreResult | null>(null);

  async function call(dryRun: boolean) {
    const iso = romeLocalToIso(before);
    if (seasonYear === null || iso === null) {
      setError(LISTONE_RESTORE_INVALID_INPUT);
      return;
    }
    if (!accessToken) {
      setError("Sessione non disponibile. Accedi di nuovo.");
      return;
    }
    setBusy(dryRun ? "preview" : "apply");
    setError(null);
    try {
      const athleteIds =
        !dryRun && preview
          ? preview.entries.filter((entry) => entry.reconstructible).map((entry) => entry.athleteId)
          : undefined;
      const result = await restoreAdminListoneRoles(accessToken, {
        seasonYear,
        before: iso,
        dryRun,
        athleteIds,
      });
      if (dryRun) {
        setPreview(result);
        setDone(null);
      } else {
        setDone(result);
        setPreview(null);
        onRestored?.();
      }
    } catch (callError) {
      setError(
        getApiErrorMessage(
          callError,
          dryRun ? "Impossibile calcolare cosa cambia." : "Ripristino dei ruoli non riuscito.",
        ),
      );
    } finally {
      setBusy(null);
      setConfirming(false);
    }
  }

  const toRestore = preview?.counts.toRestore ?? 0;

  return (
    <View style={styles.section} testID="admin-listone-restore">
      <Text style={styles.sectionTitle}>{LISTONE_RESTORE_TITLE}</Text>
      <Text style={styles.meta}>{LISTONE_RESTORE_INTRO}</Text>
      <DateTimeField
        label={LISTONE_RESTORE_BEFORE_LABEL}
        value={before}
        onChange={(next) => {
          setBefore(next);
          setPreview(null);
          setConfirming(false);
        }}
        testID="admin-listone-restore-before"
      />
      <Pressable
        style={[styles.secondaryButton, busy !== null && styles.disabled]}
        disabled={busy !== null}
        onPress={() => void call(true)}
        testID="admin-listone-restore-preview"
      >
        <Text style={styles.secondaryButtonLabel}>
          {busy === "preview" ? "Calcolo…" : LISTONE_RESTORE_PREVIEW_LABEL}
        </Text>
      </Pressable>

      {error ? (
        <UiStatePanel
          state="error"
          title="Operazione non riuscita"
          message={error}
          testID="admin-listone-restore-error"
        />
      ) : null}

      {done ? (
        <UiStatePanel
          state="success"
          title="Ruoli ripristinati"
          message={listoneRestoreDoneMessage(done.counts)}
          testID="admin-listone-restore-done"
        />
      ) : null}

      {preview ? (
        <View style={local.previewBox} testID="admin-listone-restore-result">
          <Text style={styles.meta} testID="admin-listone-restore-summary">
            {listoneRestoreSummary(preview.counts)}
          </Text>
          {preview.entries.length === 0 ? (
            <UiStatePanel
              state="empty"
              title="Niente da ripristinare"
              message={listoneRestoreEmptyMessage(before)}
              testID="admin-listone-restore-empty"
            />
          ) : (
            preview.entries.map((entry) => (
              <View
                key={entry.athleteId}
                style={styles.listRow}
                testID={`admin-listone-restore-row-${entry.athleteId}`}
              >
                <Text style={styles.name}>{entry.name}</Text>
                <Text style={styles.meta}>Club: {entry.club ?? "—"}</Text>
                <View style={local.roles}>
                  <Text style={styles.meta}>Ruolo ora</Text>
                  <RoleChip role={entry.currentRole} />
                  <Text style={styles.meta}>Ruolo di prima</Text>
                  <RoleChip role={entry.restoredRole} />
                </View>
                {entry.restoredClub && entry.restoredClub !== entry.club ? (
                  <Text style={styles.meta}>(rosa {entry.restoredClub})</Text>
                ) : null}
                <Text style={styles.meta}>
                  In rosa nelle leghe:{" "}
                  {entry.inRosters.length > 0 ? entry.inRosters.join(", ") : "—"}
                </Text>
              </View>
            ))
          )}
          {!confirming ? (
            <Pressable
              style={[styles.button, (toRestore === 0 || busy !== null) && styles.disabled]}
              disabled={toRestore === 0 || busy !== null}
              onPress={() => setConfirming(true)}
              testID="admin-listone-restore-apply"
            >
              <Text style={styles.buttonLabel}>{LISTONE_RESTORE_APPLY_LABEL}</Text>
            </Pressable>
          ) : (
            <View style={styles.confirmBox} testID="admin-listone-restore-confirm">
              <Text style={styles.meta} testID="admin-listone-restore-confirm-text">
                {listoneRestoreConfirmText(toRestore, before)}
              </Text>
              <View style={styles.rowActions}>
                <Pressable
                  style={[local.dangerButton, busy !== null && styles.disabled]}
                  disabled={busy !== null}
                  onPress={() => void call(false)}
                  testID="admin-listone-restore-confirm-yes"
                >
                  <Text style={local.dangerLabel}>
                    {busy === "apply" ? "Ripristino…" : LISTONE_RESTORE_CONFIRM_YES_LABEL}
                  </Text>
                </Pressable>
                <Pressable
                  style={[styles.secondaryButton, busy !== null && styles.disabled]}
                  disabled={busy !== null}
                  onPress={() => setConfirming(false)}
                  testID="admin-listone-restore-confirm-no"
                >
                  <Text style={styles.secondaryButtonLabel}>{LISTONE_RESTORE_CONFIRM_NO_LABEL}</Text>
                </Pressable>
              </View>
            </View>
          )}
        </View>
      ) : null}
    </View>
  );
}

const local = lazyStyles(() => StyleSheet.create({
  option: {
    flexDirection: "row",
    alignItems: "flex-start",
    gap: spacing.sm,
    marginTop: spacing.sm,
    padding: spacing.md,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.xl,
    backgroundColor: colors.background,
  },
  optionOn: {
    borderColor: colors.accent,
  },
  optionText: {
    flex: 1,
    gap: 2,
  },
  optionTitle: {
    color: colors.foreground,
    fontWeight: typography.fontWeight.semibold,
  },
  radio: {
    width: 20,
    height: 20,
    marginTop: 2,
    borderRadius: 10,
    borderWidth: 2,
    borderColor: colors.border,
    alignItems: "center",
    justifyContent: "center",
  },
  radioOn: {
    borderColor: colors.accent,
  },
  radioDot: {
    width: 10,
    height: 10,
    borderRadius: 5,
    backgroundColor: colors.accent,
  },
  warning: {
    color: colors.warning,
    fontSize: typography.fontSize.sm,
  },
  roles: {
    flexDirection: "row",
    flexWrap: "wrap",
    alignItems: "center",
    gap: spacing.xs,
  },
  roleChip: {
    overflow: "hidden",
    paddingHorizontal: spacing.sm,
    paddingVertical: 2,
    borderRadius: radius.pill,
    borderWidth: 1,
    borderColor: colors.accent,
    color: colors.foreground,
    fontSize: typography.fontSize.sm,
    fontWeight: typography.fontWeight.semibold,
  },
  roleChipWarn: {
    borderColor: colors.warning,
  },
  previewBox: {
    gap: spacing.sm,
  },
  dangerButton: {
    minHeight: 44,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    borderWidth: 1,
    borderColor: colors.danger,
    borderRadius: radius.pill,
    alignItems: "center",
    justifyContent: "center",
  },
  dangerLabel: {
    color: colors.danger,
    fontWeight: typography.fontWeight.semibold,
  },
}));
