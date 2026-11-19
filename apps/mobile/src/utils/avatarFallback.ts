/**
 * Immagine da mostrare in un avatar, o `null` per mostrare le iniziali.
 *
 * `failedSrc` è l'ultimo indirizzo che non si è caricato (es. file in 404):
 * per quello si torna alle iniziali invece di lasciare un cerchio vuoto
 * (QA 19/11). Si confronta l'indirizzo e non un semplice flag, così un nuovo
 * avatar caricato dall'utente viene riprovato.
 */
export function visibleAvatarSrc(
  src: string | null | undefined,
  failedSrc: string | null | undefined,
): string | null {
  if (!src) {
    return null;
  }
  return src === failedSrc ? null : src;
}
