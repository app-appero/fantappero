/**
 * Link che aprono l'app (QA emulatore 18/11: prima non ne gestiva nessuno).
 *
 * Le email del backend contengono link web (`/accedi/verifica`, `/accedi/reimposta-password`,
 * `/leghe/invito`): con gli App Link di Android, sul telefono con l'app installata gli stessi
 * link aprono la schermata giusta dell'app; senza app restano pagine web. Lo schema
 * `fantappero://` serve per le prove (`adb shell am start -d ...`). Il ritorno da Google
 * (`fantappero://google-auth`) non passa da qui: lo gestisce `useGoogleAuth`.
 */

/** Domini web di tutti gli ambienti. Produzione: fantappero.it (con e senza www). */
export const APP_LINK_PREFIXES = [
  "fantappero://",
  "https://dev.fantappero.it",
  "https://fantappero-web-dev.up.railway.app",
  "https://pilota.fantappero.it",
  "https://fantappero.it",
  "https://www.fantappero.it",
] as const;

export type AppLinkRoute =
  | { name: "AuthVerifyEmail"; params: { token: string } }
  | { name: "AuthResetPassword"; params: { token: string } }
  | { name: "JoinLeague"; params: { token: string } };

/** Cosa fare con un link, in base a chi è collegato. */
export type AppLinkPlan =
  | { kind: "open"; route: AppLinkRoute }
  | { kind: "after-login"; route: AppLinkRoute }
  | { kind: "ignore" };

/** Il percorso di un link (già senza dominio) → schermata dell'app, se ce n'è una. */
export function routeForAppLinkPath(path: string): AppLinkRoute | null {
  let url: URL;
  try {
    url = new URL(path.replace(/^\/*/, "/"), "https://app.invalid");
  } catch {
    return null;
  }
  const token = url.searchParams.get("token")?.trim() ?? "";
  if (!token) {
    return null;
  }
  const route = url.pathname.replace(/\/+$/, "");
  if (route === "/accedi/verifica") {
    return { name: "AuthVerifyEmail", params: { token } };
  }
  if (route === "/accedi/reimposta-password") {
    return { name: "AuthResetPassword", params: { token } };
  }
  if (route === "/leghe/invito") {
    return { name: "JoinLeague", params: { token } };
  }
  return null;
}

/** Un link completo → schermata, solo se è di uno dei nostri domini (o dello schema app). */
export function routeForAppLinkUrl(url: string | null | undefined): AppLinkRoute | null {
  if (!url) {
    return null;
  }
  for (const prefix of APP_LINK_PREFIXES) {
    if (!url.toLowerCase().startsWith(prefix)) {
      continue;
    }
    const rest = url.slice(prefix.length);
    // "https://dev.fantappero.it.altro.com/..." non è nostro: dopo il dominio serve / ? o fine.
    if (prefix !== "fantappero://" && rest !== "" && !/^[/?#]/.test(rest)) {
      continue;
    }
    return routeForAppLinkPath(rest);
  }
  return null;
}

/**
 * - verifica email e nuova password esistono solo prima dell'accesso;
 * - l'invito esiste solo dopo l'accesso: senza sessione resta in attesa fino al login.
 */
export function planAppLink(route: AppLinkRoute | null, authenticated: boolean): AppLinkPlan {
  if (!route) {
    return { kind: "ignore" };
  }
  if (route.name === "JoinLeague") {
    return authenticated ? { kind: "open", route } : { kind: "after-login", route };
  }
  return authenticated ? { kind: "ignore" } : { kind: "open", route };
}
