import { Pressable, Text, View } from "react-native";
import { rosterStyles as styles } from "./rosterStyles";

export type RosterSection = "rosa" | "listone" | "storico";

export function RosterSectionTabs({
  pageSection,
  onSelect,
  showListone,
}: {
  pageSection: RosterSection;
  onSelect: (section: RosterSection) => void;
  /** Il Listone (inserimento manuale rose) è solo per chi può modificare le rose. */
  showListone: boolean;
}) {
  const items: Array<{ id: RosterSection; label: string }> = [
    { id: "rosa", label: "Rosa" },
    ...(showListone ? [{ id: "listone" as const, label: "Listone" }] : []),
    { id: "storico", label: "Storico" },
  ];
  return (
    <View style={styles.chipRow} testID="roster-section-tabs">
      {items.map((item) => (
        <Pressable
          key={item.id}
          style={[styles.chip, pageSection === item.id && styles.chipSelected]}
          onPress={() => onSelect(item.id)}
          testID={`roster-section-${item.id}`}
        >
          <Text style={[styles.chipLabel, pageSection === item.id && styles.chipLabelSelected]}>
            {item.label}
          </Text>
        </Pressable>
      ))}
    </View>
  );
}
