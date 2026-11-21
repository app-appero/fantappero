import { useState, type ReactNode } from "react";
import { Image, type ImageStyle, type StyleProp } from "react-native";
import { visibleAvatarSrc } from "../utils/avatarFallback";

/**
 * Foto profilo che non resta mai un cerchio vuoto: se manca o non si carica (es. 404)
 * mostra `fallback`, di solito le iniziali. Come `AvatarWithFallback` del web e come
 * `TeamAvatar`: ricorda solo l'indirizzo fallito, così un avatar nuovo viene riprovato.
 */
export function AvatarWithFallback({
  src,
  style,
  fallback,
  cache,
  testID,
  accessibilityLabel,
}: {
  src: string | null | undefined;
  style: StyleProp<ImageStyle>;
  fallback: ReactNode;
  /** Politica di cache dell'immagine (es. «reload» subito dopo un caricamento). */
  cache?: "default" | "reload" | "force-cache" | "only-if-cached";
  testID?: string;
  accessibilityLabel?: string;
}) {
  const [failedSrc, setFailedSrc] = useState<string | null>(null);
  const visible = visibleAvatarSrc(src, failedSrc);
  if (!visible) {
    return <>{fallback}</>;
  }
  return (
    <Image
      source={{ uri: visible, cache }}
      style={style}
      testID={testID}
      accessibilityLabel={accessibilityLabel}
      onError={() => setFailedSrc(visible)}
    />
  );
}
