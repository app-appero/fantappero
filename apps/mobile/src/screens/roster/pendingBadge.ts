/**
 * Colori del badge «In attesa (fuori rosa)»: gli stessi del badge «In attesa» del web
 * (`fa-badge--warning`), fissi in entrambi i temi. Il testo ambra senza fondo si leggeva a 3,3:1
 * sulla scheda bianca del tema chiaro (QA 19-20/11); fondo ambra scuro e testo blu notte arrivano
 * a 5,8:1 sia in chiaro sia in scuro.
 */
export const PENDING_BADGE_COLORS = { background: "#b8860b", text: "#06121f" } as const;
