import { useState, type ReactNode } from "react";

export type AvatarWithFallbackProps = {
  /** Indirizzo dell'immagine; se manca si mostra subito il fallback. */
  src: string | null | undefined;
  /** Mostrato quando non c'è immagine o quando non si carica (es. 404): di solito le iniziali. */
  fallback: ReactNode;
  className?: string;
  /** Vuoto = immagine decorativa, nascosta ai lettori di schermo. */
  alt?: string;
};

/**
 * Avatar che non resta mai un'immagine rotta: se `src` va in errore si passa al
 * `fallback`. Ricorda solo l'indirizzo fallito, così con un indirizzo nuovo riprova.
 */
export function AvatarWithFallback({ src, fallback, className, alt = "" }: AvatarWithFallbackProps) {
  const [failedSrc, setFailedSrc] = useState<string | null>(null);
  if (!src || src === failedSrc) {
    return <>{fallback}</>;
  }
  return (
    <img
      className={className}
      src={src}
      alt={alt}
      aria-hidden={alt ? undefined : "true"}
      onError={() => setFailedSrc(src)}
    />
  );
}
