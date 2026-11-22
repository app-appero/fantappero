import type { AthleteMarketFields } from "@fantappero/contracts";
import { theme } from "@fantappero/ui/theme";
import type { ReactNode } from "react";
import { StyleSheet, Text, View, type StyleProp, type ViewStyle } from "react-native";
import { lazyStyles } from "../theme/lazyStyles";
import { athleteMarketTags, isEmptyMarketTags, type SeasonAverageDisplay } from "./athleteValue";

const { colors, radius, typography } = theme;

/** Etichetta della media: verde se della stagione in corso, rossa con l'anno se della scorsa. */
export function SeasonAverageChip({
  average,
  testID,
}: {
  average: SeasonAverageDisplay;
  testID?: string;
}) {
  const current = average.tone === "current";
  return (
    <View
      style={[styles.chip, current ? styles.averageCurrent : styles.averagePrevious]}
      accessible
      accessibilityLabel={average.accessibilityLabel}
      testID={testID}
    >
      <Text style={[styles.label, { color: current ? colors.success : colors.danger }]} numberOfLines={1}>
        Media {average.text}
      </Text>
    </View>
  );
}

/** «Valore 58». */
export function MarketValueChip({ label, testID }: { label: string; testID?: string }) {
  return (
    <View style={[styles.chip, styles.value]} accessible accessibilityLabel={label} testID={testID}>
      <Text style={[styles.label, { color: colors.warning }]} numberOfLines={1}>
        {label}
      </Text>
    </View>
  );
}

/**
 * Valore e media stagionale di un calciatore nelle righe del mercato (1.3): ognuna solo se c'è.
 * `leading` sono le etichette che vengono prima (es. «Libero»), sulla stessa riga che va a capo.
 */
export function AthleteMarketTags({
  fields,
  showValue = true,
  leading,
  style,
  testID,
}: {
  fields: AthleteMarketFields | null | undefined;
  /** `false` dove il Valore non serve (resta la media). */
  showValue?: boolean;
  leading?: ReactNode;
  style?: StyleProp<ViewStyle>;
  testID?: string;
}) {
  const tags = athleteMarketTags(fields);
  const valueLabel = showValue ? tags.valueLabel : null;
  if (!leading && (isEmptyMarketTags(tags) || (!valueLabel && !tags.average))) {
    return null;
  }
  return (
    <View style={[styles.row, style]} testID={testID}>
      {leading}
      {valueLabel ? <MarketValueChip label={valueLabel} testID={testID ? `${testID}-value` : undefined} /> : null}
      {tags.average ? (
        <SeasonAverageChip average={tags.average} testID={testID ? `${testID}-average` : undefined} />
      ) : null}
    </View>
  );
}

const styles = lazyStyles(() =>
  StyleSheet.create({
    row: {
      flexDirection: "row",
      flexWrap: "wrap",
      alignItems: "center",
      gap: 4,
      marginTop: 3,
    },
    chip: {
      paddingHorizontal: 7,
      paddingVertical: 1,
      borderRadius: radius.pill,
      borderWidth: 1,
      maxWidth: "100%",
    },
    value: {
      borderColor: colors.warning,
    },
    averageCurrent: {
      borderColor: colors.success,
    },
    averagePrevious: {
      borderColor: colors.danger,
    },
    label: {
      fontSize: 11,
      fontWeight: typography.fontWeight.bold,
      fontVariant: ["tabular-nums"],
    },
  }),
);
