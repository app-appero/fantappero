/**
 * Dove portare l'operatore dopo l'impersonificazione dall'elenco segnalazioni:
 * sulla pagina in cui l'utente ha incontrato il problema, se è un percorso
 * interno dell'app; altrimenti sulle leghe. Mai aree operatore o link esterni.
 */
const FALLBACK = "/leghe";

export function impersonationDestination(pageContext: string | null | undefined): string {
  const path = (pageContext ?? "").trim();
  if (
    !path.startsWith("/") ||
    path.startsWith("//") ||
    path.includes("://") ||
    path.includes("\\") ||
    path === "/admin" ||
    path.startsWith("/admin/") ||
    path.startsWith("/accedi") ||
    path.startsWith("/feedback")
  ) {
    return FALLBACK;
  }
  return path;
}
