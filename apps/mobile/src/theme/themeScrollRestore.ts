/**
 * Il Profilo resta dov'era dopo il cambio tema.
 *
 * Al cambio tema App.tsx rimonta tutta la navigazione (`key={scheme}`, vedi `lazyStyles.ts`):
 * la schermata resta la stessa grazie a `initialState`, ma il suo ScrollView è nuovo e la
 * pagina ripartiva dall'alto (QA 22/11). Il Profilo segna qui dov'era prima di cambiare tema
 * e la sua copia rimontata ci torna appena la pagina è di nuovo lunga abbastanza.
 *
 * Solo logica pura: gira nei test `node:test`.
 */

/** Oltre questo tempo un punto segnato e mai usato non vale più (es. tema senza rimontaggio). */
export const THEME_SCROLL_TTL_MS = 20_000;

let pending: { y: number; at: number } | null = null;

/** Prima di cambiare tema: dove si trova la pagina del Profilo. */
export function rememberScrollBeforeThemeChange(y: number, now: number = Date.now()): void {
  pending = { y: Math.max(0, y), at: now };
}

/** Punto da ritrovare dopo il rimontaggio, se segnato da poco; non lo consuma. */
export function pendingThemeScroll(now: number = Date.now()): number | null {
  if (!pending || now - pending.at > THEME_SCROLL_TTL_MS) {
    return null;
  }
  return pending.y;
}

export function clearThemeScroll(): void {
  pending = null;
}

/** Dove scorrere: il punto di prima, entro la fine della pagina. */
export function themeScrollTarget(y: number, contentHeight: number, viewportHeight: number): number {
  const maxOffset = Math.max(0, contentHeight - viewportHeight);
  return Math.min(Math.max(0, y), maxOffset);
}
