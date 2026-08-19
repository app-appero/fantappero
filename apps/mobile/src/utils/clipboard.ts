import { Share } from "react-native";

/** Condivide/copia testo via sheet nativa (clipboard RN senza dipendenze extra). */
export async function copyToClipboard(value: string): Promise<void> {
  const result = await Share.share({ message: value });
  if (result.action === Share.dismissedAction) {
    throw new Error("clipboard unavailable");
  }
}
