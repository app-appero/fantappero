import { Pressable, Text, View } from "react-native";
import { rosterStyles as styles } from "./rosterStyles";

export function RosterSectionTabs({
  pageSection,
  onSelect,
}: {
  pageSection: "rosa" | "storico";
  onSelect: (section: "rosa" | "storico") => void;
}) {
  return (
    <View style={styles.chipRow} testID="roster-section-tabs">
      <Pressable
        style={[styles.chip, pageSection === "rosa" && styles.chipSelected]}
        onPress={() => onSelect("rosa")}
        testID="roster-section-rosa"
      >
        <Text style={[styles.chipLabel, pageSection === "rosa" && styles.chipLabelSelected]}>
          Rosa
        </Text>
      </Pressable>
      <Pressable
        style={[styles.chip, pageSection === "storico" && styles.chipSelected]}
        onPress={() => onSelect("storico")}
        testID="roster-section-storico"
      >
        <Text style={[styles.chipLabel, pageSection === "storico" && styles.chipLabelSelected]}>
          Storico
        </Text>
      </Pressable>
    </View>
  );
}
