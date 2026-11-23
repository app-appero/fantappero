import {
  EMPTY_APP_VERSION_FORM,
  appVersionFormFrom,
  appVersionSavedMessage,
  appVersionUpdateFrom,
  validateAppVersionForm,
  type AdminAppUsage,
  type AppVersionFormErrors,
  type AppVersionFormFields,
  type AppVersionInfo,
} from "@fantappero/contracts";
import { theme } from "@fantappero/ui/theme";
import { useCallback, useState } from "react";
import { Pressable, StyleSheet, Text, View, type KeyboardTypeOptions } from "react-native";
import { adminUiStyles } from "../../admin/adminUiStyles";
import {
  fetchAppVersionConfig,
  fetchAppVersionUsers,
  saveAppVersionConfig,
} from "../../api/appVersion";
import { ApiError } from "../../api/client";
import { AppTextInput as TextInput } from "../../components/AppTextInput";
import { UiStatePanel } from "../../components/UiStatePanel";
import { useScreenData } from "../../hooks/useScreenData";
import { PageContainer } from "../../layout/PageContainer";
import { getApiErrorMessage, useAuthSession } from "../../session/DemoSessionContext";
import { lazyStyles } from "../../theme/lazyStyles";
import { AppUsageList } from "./AppUsageList";

const { colors, spacing, typography } = theme;

type FieldKey = keyof AppVersionFormFields;

const FIELDS: {
  key: FieldKey;
  label: string;
  keyboardType?: KeyboardTypeOptions;
  maxLength?: number;
}[] = [
  { key: "name", label: "Versione (es. 1.3.0)", keyboardType: "decimal-pad" },
  { key: "code", label: "versionCode Android", keyboardType: "number-pad" },
  { key: "url", label: "Link di download (https)", keyboardType: "url" },
  { key: "message", label: "Messaggio breve (facoltativo)", maxLength: 200 },
];

/**
 * Pannello operatore → «Versione app» (release 1.4, canvas «Pannello operatore»): lo stesso
 * modulo del sito (versione, versionCode, link di download e messaggio), con la stessa
 * chiamata `PUT /admin/app-version`. Prima nell'app l'operatore non poteva annunciare una
 * versione.
 *
 * Decisione di Rosario del 23/11: salvare una versione nuova manda anche la notifica a chi non
 * ce l'ha (il messaggio dice a quanti) e sotto il modulo c'è «Chi ha quale versione», come sul
 * sito.
 */
export function AdminAppVersionScreen() {
  const { accessToken } = useAuthSession();
  const [current, setCurrent] = useState<AppVersionInfo | null>(null);
  const [fields, setFields] = useState<AppVersionFormFields>(EMPTY_APP_VERSION_FORM);
  const [errors, setErrors] = useState<AppVersionFormErrors>({});
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [usage, setUsage] = useState<AdminAppUsage | null>(null);
  const [usageError, setUsageError] = useState<string | null>(null);

  const loadUsage = useCallback(async (token: string) => {
    try {
      setUsage(await fetchAppVersionUsers(token));
      setUsageError(null);
    } catch (cause) {
      setUsageError(getApiErrorMessage(cause, "Impossibile leggere chi ha quale versione."));
    }
  }, []);

  const load = useCallback(async () => {
    setLoading(true);
    setLoadError(null);
    if (!accessToken) {
      setLoadError("Sessione non disponibile. Accedi di nuovo.");
      setLoading(false);
      return;
    }
    try {
      const usageLoad = loadUsage(accessToken);
      const info = await fetchAppVersionConfig(accessToken);
      setCurrent(info);
      setFields(appVersionFormFrom(info));
      await usageLoad;
    } catch (cause) {
      setLoadError(
        cause instanceof ApiError && cause.status === 403
          ? "Non hai i permessi per cambiare la versione dell'app."
          : getApiErrorMessage(cause, "Impossibile leggere la versione dell'app."),
      );
    } finally {
      setLoading(false);
    }
  }, [accessToken, loadUsage]);

  const { refreshing, onRefresh } = useScreenData(load);

  function update(key: FieldKey, value: string) {
    setFields((previous) => ({ ...previous, [key]: value }));
    setErrors((previous) => ({ ...previous, [key]: undefined }));
  }

  async function save() {
    setMessage(null);
    setSaveError(null);
    const found = validateAppVersionForm(fields);
    setErrors(found);
    if (Object.keys(found).length > 0) {
      return;
    }
    if (!accessToken) {
      setSaveError("Sessione non disponibile. Accedi di nuovo.");
      return;
    }
    setBusy(true);
    try {
      const saved = await saveAppVersionConfig(accessToken, appVersionUpdateFrom(fields));
      setCurrent(saved);
      setFields(appVersionFormFrom(saved));
      setMessage(appVersionSavedMessage(saved));
      void loadUsage(accessToken);
    } catch (cause) {
      setSaveError(getApiErrorMessage(cause, "Salvataggio non riuscito."));
    } finally {
      setBusy(false);
    }
  }

  const android = current?.android ?? null;

  return (
    <PageContainer
      title="Versione app"
      testID="screen-admin-app-version"
      refreshing={refreshing}
      onRefresh={onRefresh}
    >
      {loading ? (
        <UiStatePanel
          state="loading"
          title="Caricamento"
          message="Recupero la versione annunciata…"
          testID="admin-appversion-loading"
        />
      ) : null}
      {!loading && loadError ? (
        <UiStatePanel
          state={loadError.includes("permessi") ? "forbidden" : "error"}
          title="Versione non disponibile"
          message={loadError}
          testID="admin-appversion-error"
        />
      ) : null}
      {!loading && !loadError ? (
        <View style={styles.form} testID="admin-appversion">
          <Text style={adminUiStyles.meta}>
            Quando pubblichi un nuovo APK, aggiorna qui versione e link: chi non ha ancora quella
            versione riceve una notifica (nell&apos;elenco e push) e, a ogni ingresso nell&apos;app,
            l&apos;avviso con «Scarica».
          </Text>
          <Text style={styles.current} testID="admin-appversion-current">
            {android
              ? `Ora annunciata: ${android.latestVersionName} (versionCode ${android.latestVersionCode}).`
              : "Nessuna versione impostata: nell'app non compare nessun avviso."}
          </Text>
          {FIELDS.map((field) => {
            const fieldError = errors[field.key];
            return (
              <View key={field.key} style={styles.field}>
                <Text style={styles.label} nativeID={`admin-appversion-label-${field.key}`}>
                  {field.label}
                </Text>
                <TextInput
                  style={[adminUiStyles.input, fieldError ? styles.inputError : null]}
                  value={fields[field.key]}
                  onChangeText={(value) => update(field.key, value)}
                  editable={!busy}
                  autoCapitalize="none"
                  autoCorrect={false}
                  keyboardType={field.keyboardType}
                  maxLength={field.maxLength}
                  accessibilityLabel={field.label}
                  accessibilityLabelledBy={`admin-appversion-label-${field.key}`}
                  testID={`admin-appversion-${field.key}`}
                />
                {fieldError ? (
                  <Text style={styles.error} testID={`admin-appversion-${field.key}-error`}>
                    {fieldError}
                  </Text>
                ) : null}
              </View>
            );
          })}
          <Pressable
            accessibilityRole="button"
            accessibilityState={{ disabled: busy, busy }}
            disabled={busy}
            onPress={() => void save()}
            style={({ pressed }) => [
              adminUiStyles.button,
              styles.save,
              (busy || pressed) && adminUiStyles.disabled,
            ]}
            testID="admin-appversion-save"
          >
            <Text style={adminUiStyles.buttonLabel}>{busy ? "Salvataggio…" : "Salva"}</Text>
          </Pressable>
          {message ? (
            <Text
              style={styles.success}
              accessibilityLiveRegion="polite"
              testID="admin-appversion-saved"
            >
              {message}
            </Text>
          ) : null}
          {saveError ? (
            <Text
              style={styles.error}
              accessibilityLiveRegion="assertive"
              testID="admin-appversion-save-error"
            >
              {saveError}
            </Text>
          ) : null}
        </View>
      ) : null}
      {!loading && !loadError && usage ? <AppUsageList usage={usage} /> : null}
      {!loading && !loadError && usageError ? (
        <UiStatePanel
          state="error"
          title="Elenco non disponibile"
          message={usageError}
          testID="admin-appversion-users-error"
        />
      ) : null}
    </PageContainer>
  );
}

const styles = lazyStyles(() =>
  StyleSheet.create({
    form: {
      gap: spacing.md,
    },
    current: {
      color: colors.foreground,
      fontSize: typography.fontSize.sm,
      fontWeight: typography.fontWeight.semibold,
    },
    field: {
      gap: spacing.xs,
    },
    label: {
      color: colors.foregroundMuted,
      fontSize: typography.fontSize.sm,
    },
    inputError: {
      borderColor: colors.danger,
    },
    error: {
      color: colors.danger,
      fontSize: typography.fontSize.sm,
    },
    success: {
      color: colors.success,
      fontSize: typography.fontSize.sm,
      fontWeight: typography.fontWeight.semibold,
    },
    save: {
      alignSelf: "stretch",
    },
  }),
);
