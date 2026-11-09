import { Image, type ImageStyle, type StyleProp } from "react-native";
import { SvgXml } from "react-native-svg";
import { useMemo } from "react";

const SVG_PREFIX = "data:image/svg+xml;utf8,";

/**
 * Immagine del calciatore: l'avatar SVG generato dal client (`playerAvatarUrl`)
 * si disegna con react-native-svg (React Native non legge gli SVG da URL `data:`);
 * qualsiasi altro URL resta un'immagine normale.
 */
export function AvatarImage({
  uri,
  style,
  size,
}: {
  uri: string;
  style?: StyleProp<ImageStyle>;
  /** Lato in pixel; se assente l'immagine riempie il contenitore. */
  size?: number;
}) {
  const xml = useMemo(
    () => (uri.startsWith(SVG_PREFIX) ? decodeURIComponent(uri.slice(SVG_PREFIX.length)) : null),
    [uri],
  );
  if (xml) {
    return <SvgXml xml={xml} width={size ?? "100%"} height={size ?? "100%"} />;
  }
  return <Image source={{ uri }} style={style} />;
}
