import Feather from "@expo/vector-icons/Feather";
import { theme } from "@fantappero/ui/theme";
import { Pressable } from "react-native";
import { rosterStyles as styles } from "./rosterStyles";

const { colors } = theme;

/** Azione compatta di riga: più per assegnare, x per rimuovere. */
export function RosterActionBadge({
  action,
  disabled,
  onPress,
  testID,
  accessibilityLabel,
}: {
  action: "assign" | "release";
  disabled?: boolean;
  onPress: () => void;
  testID: string;
  accessibilityLabel: string;
}) {
  const release = action === "release";
  return (
    <Pressable
      style={[
        styles.rowActionBadge,
        release ? styles.rowActionRelease : styles.rowActionAssign,
        disabled && styles.disabled,
      ]}
      disabled={disabled}
      accessibilityRole="button"
      accessibilityLabel={accessibilityLabel}
      testID={testID}
      onPress={onPress}
    >
      <Feather name={release ? "x" : "plus"} size={16} color={colors.accentContrast} />
    </Pressable>
  );
}
