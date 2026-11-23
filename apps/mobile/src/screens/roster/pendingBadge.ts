/**
 * Colori del badge «In esubero» (prima «In attesa (fuori rosa)», Rosario 23/11): gli stessi del
 * badge «In esubero» del web (`fa-badge--warning`), fissi in entrambi i temi. Il testo ambra
 * senza fondo si leggeva a 3,3:1 sulla scheda bianca del tema chiaro (QA 19-20/11); fondo ambra
 * scuro e testo blu notte arrivano a 5,8:1 sia in chiaro sia in scuro.
 */
export const PENDING_BADGE_COLORS = { background: "#b8860b", text: "#06121f" } as const;

/**
 * La scritta del badge del giocatore in esubero in Rosa, con accanto il «?» che apre «Ho un
 * giocatore «in esubero»: cosa faccio?». La stessa del sito; prima era «In attesa (fuori rosa)»
 * (Rosario, 23/11).
 */
export const PENDING_BADGE_LABEL = "In esubero";
