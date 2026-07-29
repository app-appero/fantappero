import type { SupportedLanguage } from "./index.ts";

/** Default UI locale for web and mobile clients. */
export const DEFAULT_UI_LOCALE: SupportedLanguage = "it";

export const LANGUAGE_LABELS: Record<SupportedLanguage, string> = {
  it: "Italiano",
  en: "English",
  es: "Español",
  fr: "Français",
  de: "Deutsch",
};

const it = {
  loading: "Caricamento…",
  saving: "Salvataggio…",
  working: "Operazione in corso…",
  networkError: "Impossibile contattare l'API.",
  fillForm: "Compila il modulo per continuare.",
  fillEmailPassword: "Inserisci email e password.",

  signedIn: "Accesso effettuato.",
  welcomeBack: "Bentornato.",
  accountCreated: "Account creato.",
  loggedOut: "Disconnessione effettuata.",
  emailVerified: "Email verificata.",
  accountDeleted: "Account eliminato.",

  signInTitle: "Accedi per giocare",
  accountTitle: "Il tuo account",
  profileTitle: "Impostazioni profilo",
  privacyTitle: "Privacy e dati",

  email: "Email",
  password: "Password",
  name: "Nome",
  verified: "Verificata",
  yes: "sì",
  no: "no",

  signIn: "Accedi",
  createAccount: "Crea account",
  needAccount: "Non hai un account? Registrati",
  alreadyRegistered: "Già registrato? Accedi",
  forgotPassword: "Password dimenticata",
  sendResetLink: "Invia link di reset",
  resetToken: "Token di reset",
  newPassword: "Nuova password",
  updatePassword: "Aggiorna password",
  verificationToken: "Token di verifica",
  verifyEmail: "Verifica email",

  editProfile: "Modifica profilo",
  privacyAndData: "Privacy e dati",
  logOut: "Esci",
  backToAccount: "Torna all'account",

  noAvatar: "Nessun avatar.",
  avatar: "Avatar",
  displayName: "Nome visualizzato",
  language: "Lingua",
  timezone: "Fuso orario",
  emailNotifications: "Notifiche email",
  pushNotifications: "Notifiche push",
  policyAccepted: "Informativa accettata",
  acceptPolicy: "Accetta informativa privacy v",
  saveProfile: "Salva profilo",
  profileSaved: "Profilo salvato.",
  avatarUpdated: "Avatar aggiornato.",
  profileEmptyChange: "Modifica almeno un campo prima di salvare.",
  unableUploadAvatar: "Impossibile caricare l'avatar.",

  yourData: "I tuoi dati",
  privacyIntro:
    "Scarica una copia dei tuoi dati o elimina definitivamente l'account. Lo storico di lega resta intatto; i dati personali vengono anonimizzati.",
  exportMyData: "Esporta i miei dati",
  exportReady: (count: number) => `Export pronto (${count} iscrizioni a leghe).`,
  noExportYet: "Nessun export ancora.",
  deleteAccount: "Elimina account",
  deleteConfirmHint: "Inserisci la password per confermare l'eliminazione.",
  deleteConfirmCheckbox: "Comprendo che questa azione è irreversibile",
  deleteMyAccount: "Elimina il mio account",

  createLeagueTitle: "Crea una lega",
  leagueName: "Nome lega",
  seasonYear: "Stagione (anno di inizio)",
  competitions: "Campionati",
  selectCompetitionsHint: (min: number) => `Seleziona almeno ${min} campionati.`,
  createLeague: "Crea lega in bozza",
  leagueCreated: "Lega creata in bozza.",
  leagueEmptyForm: "Compila nome, stagione e almeno tre campionati.",
  createLeagueLink: "Crea lega",
  emailNotVerified: "Verifica l'email prima di creare una lega.",
  emailNotVerifiedHint:
    "Dopo la registrazione il link di verifica compare nei log dell'API (ambiente di sviluppo).",
  goVerifyEmail: "Verifica email",
  errorEmailNotVerified: "Email non verificata.",
  errorForbidden: "Non hai i permessi per questa operazione.",
  errorLeagueValidation: "Configurazione lega non valida.",

  register: "Registrati",
  backToSignIn: "Torna all'accesso",
  createAccountLink: "Crea account",
  on: "attive",
  off: "disattive",
  acceptPolicyShort: "Accetta informativa v",
} as const;

export type UiStrings = typeof it;

const catalogs: Record<SupportedLanguage, UiStrings> = {
  it,
  en: it, // fallback until EN catalog is added
  es: it,
  fr: it,
  de: it,
};

/** Resolve UI copy for the given locale (defaults to Italian). */
export function ui(locale: SupportedLanguage = DEFAULT_UI_LOCALE): UiStrings {
  return catalogs[locale] ?? it;
}
