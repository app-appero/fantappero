/**
 * Ultima pagina dell'app vista prima di aprire «Segnala un problema»: arriva
 * ai tester come contesto della segnalazione, senza che debbano ricordarla.
 */
const KEY = "fa.feedback.lastPath";

export function rememberLastAppPath(pathname: string): void {
  if (pathname.startsWith("/feedback")) {
    return;
  }
  try {
    window.sessionStorage.setItem(KEY, pathname);
  } catch {
    // sessionStorage non disponibile: la segnalazione parte senza contesto.
  }
}

export function readLastAppPath(): string | undefined {
  try {
    return window.sessionStorage.getItem(KEY) ?? undefined;
  } catch {
    return undefined;
  }
}
