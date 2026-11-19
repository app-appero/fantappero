/**
 * Decisioni della schermata di accesso, senza React (così si provano con node:test):
 * quale disposizione mostrare, se la scheda con email parte aperta, cosa dice il separatore,
 * quando nascondere le carte e quali schede (Accedi / Registrati) ci sono.
 */

/** Come si presenta l'accesso. */
export type AuthLayout =
  /** Solo Google, come nel pilota con la registrazione email spenta (o finché il server non risponde). */
  | "google"
  /** Google in primo piano e, sotto, «Continua con email» che apre la scheda Accedi / Registrati. */
  | "google_email"
  /** Google non configurato (manca il client id o l'indirizzo del sito): solo la scheda con email. */
  | "email";

export type AuthScreenInput = {
  /** `false` finché `GET /auth/options` non ha risposto. */
  optionsLoaded: boolean;
  emailRegistrationEnabled: boolean;
  /** `useGoogleAuth().available`. */
  googleAvailable: boolean;
  /** Ultima scelta dell'utente sulla scheda con email: `null` finché non l'ha aperta o chiusa. */
  expandedChoice: boolean | null;
};

export type AuthScreenView = {
  layout: AuthLayout;
  /** La scheda con email è aperta. */
  emailExpanded: boolean;
  /** Tasto secondario «Continua con email» (scheda chiusa). */
  showEmailToggle: boolean;
  /** Scheda con Accedi / Registrati. */
  showEmailCard: boolean;
  /** Testo del separatore sotto Google; `null` se non c'è nulla da separare. */
  dividerLabel: string | null;
  /** Carte giocatore a ventaglio: a scheda aperta si nascondono, così il modulo sta nello schermo. */
  showCardsStage: boolean;
  /** «Entri in un tocco…» sotto Google: solo quando Google è l'unico accesso. */
  showGoogleNote: boolean;
};

export function resolveAuthLayout(input: Omit<AuthScreenInput, "expandedChoice">): AuthLayout {
  // Opzioni non ancora arrivate o registrazione email spenta: resta tutto come prima (solo Google).
  if (!input.optionsLoaded || !input.emailRegistrationEnabled) {
    return "google";
  }
  return input.googleAvailable ? "google_email" : "email";
}

/**
 * Scheda con email aperta o chiusa. Senza una scelta dell'utente parte chiusa, tranne quando
 * Google manca: allora è l'unico modo di entrare e si apre da sola.
 */
export function isEmailCardExpanded(layout: AuthLayout, expandedChoice: boolean | null): boolean {
  if (layout === "google") {
    return false;
  }
  return expandedChoice ?? layout === "email";
}

export function resolveAuthScreenView(input: AuthScreenInput): AuthScreenView {
  const layout = resolveAuthLayout(input);
  const emailExpanded = isEmailCardExpanded(layout, input.expandedChoice);
  const emailAccess = layout !== "google";
  return {
    layout,
    emailExpanded,
    showEmailToggle: emailAccess && !emailExpanded,
    showEmailCard: emailAccess && emailExpanded,
    // Il separatore divide Google dall'email: senza Google non serve.
    dividerLabel: layout === "google_email" ? (emailExpanded ? "oppure con email" : "oppure") : null,
    showCardsStage: !emailExpanded,
    showGoogleNote: layout === "google" && input.googleAvailable,
  };
}

/** Schede della parte con email. */
export type AuthTab = "accedi" | "registrati";

export const AUTH_TABS: ReadonlyArray<{ key: AuthTab; label: string; testID: string }> = [
  { key: "accedi", label: "Accedi", testID: "auth-tab-login" },
  { key: "registrati", label: "Registrati", testID: "auth-tab-register" },
];

/** All'apertura si parte da Accedi: chi ha già un account è il caso più comune. */
export const INITIAL_AUTH_TAB: AuthTab = "accedi";
