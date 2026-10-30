import { Image, View, type StyleProp, type ViewStyle } from "react-native";
import { roleRingColor } from "../screens/formation/FormationParts";

/**
 * Foto calciatore con anello colorato per ruolo, stesso stile della Formazione
 * (`roleRingColor` + cerchio bordato). Renderizza `null` quando `photoUrl` è
 * assente: il chiamante resta libero di mostrare il proprio fallback esistente
 * (es. pallino colorato con la lettera del ruolo).
 */
export function PlayerPhotoRing({
  photoUrl,
  role,
  size = 30,
  style,
}: {
  photoUrl: string | null | undefined;
  role: string | null | undefined;
  size?: number;
  style?: StyleProp<ViewStyle>;
}) {
  if (!photoUrl) {
    return null;
  }
  return (
    <View
      style={[
        {
          width: size,
          height: size,
          borderRadius: size / 2,
          borderWidth: 2,
          borderColor: roleRingColor(role),
          overflow: "hidden",
          backgroundColor: "#ffffff",
        },
        style,
      ]}
    >
      <Image source={{ uri: photoUrl }} style={{ width: "100%", height: "100%" }} />
    </View>
  );
}
