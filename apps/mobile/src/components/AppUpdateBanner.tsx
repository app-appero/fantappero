import {
  appUpdateBannerText,
  displayAppVersionName,
  isHttpsDownloadUrl,
  type AndroidAppVersion,
} from "@fantappero/contracts";
import { theme } from "@fantappero/ui/theme";
import { Linking, Pressable, StyleSheet, Text, View } from "react-native";
import { lazyStyles } from "../theme/lazyStyles";

const { colors, spacing, typography, radius } = theme;

/** Avviso «È disponibile la versione X dell'app» con «Scarica» e «Più tardi» (pilota-1.2). */
export function AppUpdateBanner({
  version,
  onDismiss,
}: {
  version: AndroidAppVersion;
  onDismiss: () => void;
}) {
  const name = displayAppVersionName(version.latestVersionName);
  return (
    <View style={styles.banner} accessibilityLiveRegion="polite" testID="app-update-banner">
      <Text style={styles.text}>{appUpdateBannerText(version.latestVersionName)}</Text>
      {version.message ? <Text style={styles.message}>{version.message}</Text> : null}
      <View style={styles.actions}>
        <Pressable
          accessibilityRole="button"
          accessibilityLabel={`Scarica la versione ${name} dell'app`}
          onPress={() => {
            if (isHttpsDownloadUrl(version.downloadUrl)) {
              void Linking.openURL(version.downloadUrl.trim()).catch(() => undefined);
            }
          }}
          style={({ pressed }) => [styles.button, styles.primary, pressed && styles.pressed]}
          testID="app-update-download"
        >
          <Text style={[styles.buttonLabel, styles.primaryLabel]}>Scarica</Text>
        </Pressable>
        <Pressable
          accessibilityRole="button"
          accessibilityLabel={`Più tardi: nascondi l'avviso della versione ${name}`}
          onPress={onDismiss}
          style={({ pressed }) => [styles.button, styles.secondary, pressed && styles.pressed]}
          testID="app-update-later"
        >
          <Text style={styles.buttonLabel}>Più tardi</Text>
        </Pressable>
      </View>
    </View>
  );
}

const styles = lazyStyles(() => StyleSheet.create({
  banner: {
    gap: spacing.sm,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    backgroundColor: colors.backgroundElevated,
    borderBottomWidth: 1,
    borderBottomColor: colors.accent,
  },
  text: {
    color: colors.foreground,
    fontSize: typography.fontSize.sm,
    fontWeight: typography.fontWeight.semibold,
  },
  message: {
    color: colors.foregroundMuted,
    fontSize: typography.fontSize.sm,
  },
  actions: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacing.sm,
  },
  button: {
    minHeight: 44,
    minWidth: 44,
    justifyContent: "center",
    paddingHorizontal: spacing.md,
    borderRadius: radius.pill,
    borderWidth: 1,
  },
  primary: {
    backgroundColor: colors.brand,
    borderColor: colors.brand,
  },
  secondary: {
    backgroundColor: colors.background,
    borderColor: colors.border,
  },
  pressed: {
    opacity: 0.75,
  },
  buttonLabel: {
    color: colors.foreground,
    fontWeight: typography.fontWeight.semibold,
    fontSize: typography.fontSize.sm,
  },
  primaryLabel: {
    color: colors.onBrand,
  },
}));
