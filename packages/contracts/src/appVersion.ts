/**
 * Versione dell'app Android e avviso «È disponibile la versione X» (pilota-1.2, Rosario 21/11).
 *
 * L'APK si distribuisce a mano: l'operatore scrive nel pannello l'ultima versione pubblicata
 * (`PUT /admin/app-version`), l'app la legge da `GET /app/version` e la confronta con il
 * versionCode installato. Nessun import: i test `node:test` dell'app caricano questo file dal
 * sorgente.
 */

/** Ultima versione pubblicata dell'app Android, come la imposta l'operatore. */
export interface AndroidAppVersion {
  /** Nome mostrato, es. "1.3.0". */
  latestVersionName: string;
  /** versionCode Android: è questo che si confronta con l'app installata. */
  latestVersionCode: number;
  /** Link di download dell'APK (solo https). */
  downloadUrl: string;
  /** Messaggio breve facoltativo sotto l'avviso. */
  message: string | null;
}

/** Risposta di `GET /app/version` e `GET/PUT /admin/app-version`. */
export interface AppVersionInfo {
  /** `null` se l'operatore non ha impostato nulla: nessun avviso. */
  android: AndroidAppVersion | null;
}

/**
 * Risposta di `PUT /admin/app-version` (release 1.4): la versione salvata e quante notifiche
 * «È disponibile la versione X» sono partite con questo salvataggio.
 */
export interface AppVersionSaveResult extends AppVersionInfo {
  /**
   * Notifiche nuove (0 se si risalva lo stesso versionCode); `null` se l'invio non è riuscito
   * (la versione resta salvata); assente dai server più vecchi.
   */
  notifiedUsers?: number | null;
}

/** Testo dopo «Salva» nel modulo «Versione app» (sito e app). */
export function appVersionSavedMessage(result: AppVersionSaveResult): string {
  const notified = result.notifiedUsers;
  if (notified === undefined) {
    return "Versione salvata: chi ha un'app più vecchia vedrà l'avviso.";
  }
  if (notified === null) {
    return "Versione salvata, ma la notifica non è partita. Salva di nuovo più tardi per riprovare.";
  }
  if (notified === 0) {
    return "Versione salvata. Nessuna notifica nuova: chi non ha questa versione era già stato avvisato.";
  }
  return `Versione salvata: notifica inviata a ${notified} ${notified === 1 ? "utente" : "utenti"} che non ${notified === 1 ? "ha" : "hanno"} ancora questa versione.`;
}

/** Corpo di `PUT /admin/app-version`. */
export interface AndroidAppVersionUpdate {
  latestVersionName: string;
  latestVersionCode: number;
  downloadUrl: string;
  message?: string | null;
}

function isPositiveInteger(value: unknown): value is number {
  return typeof value === "number" && Number.isInteger(value) && value > 0;
}

/**
 * Vero se la versione pubblicata è più nuova di quella installata. Senza uno dei due numeri
 * (o con valori non validi) non si può confrontare e la risposta è falsa: meglio nessun avviso
 * che un avviso sbagliato.
 */
export function isNewerAppVersion(
  installedCode: number | null | undefined,
  latestCode: number | null | undefined,
): boolean {
  if (!isPositiveInteger(installedCode) || !isPositiveInteger(latestCode)) {
    return false;
  }
  return latestCode > installedCode;
}

/** Nome da mostrare: "1.3.0" → "1.3", "2.0.0" → "2.0", "1.3.1" resta "1.3.1". */
export function displayAppVersionName(versionName: string): string {
  const parts = versionName.trim().split(".");
  while (parts.length > 2 && parts[parts.length - 1] === "0") {
    parts.pop();
  }
  return parts.join(".");
}

/** Testo dell'avviso nell'app. */
export function appUpdateBannerText(versionName: string): string {
  return `È disponibile la versione ${displayAppVersionName(versionName)} dell'app.`;
}

/** Link di download accettato: solo https, con un dominio e senza spazi (come il server). */
export function isHttpsDownloadUrl(url: string): boolean {
  return /^https:\/\/[^\s/?#:@]+(:\d+)?([/?#]\S*)?$/.test(url.trim());
}

// --- modulo «Versione app» del pannello operatore (sito e app, release 1.4) -------------------

/** I quattro campi del modulo, come li scrive l'operatore. */
export interface AppVersionFormFields {
  name: string;
  code: string;
  url: string;
  message: string;
}

export type AppVersionFormErrors = Partial<Record<keyof AppVersionFormFields, string>>;

export const EMPTY_APP_VERSION_FORM: AppVersionFormFields = { name: "", code: "", url: "", message: "" };

const VERSION_NAME_PATTERN = /^[0-9]+(\.[0-9]+){0,3}$/;
/** Come il server (`ANDROID_MAX_VERSION_CODE`). */
const MAX_VERSION_CODE = 2_100_000_000;
const MAX_MESSAGE_LENGTH = 200;

/** Campi precompilati con la versione annunciata (vuoti se non c'è). */
export function appVersionFormFrom(info: AppVersionInfo | null | undefined): AppVersionFormFields {
  const android = info?.android;
  return android
    ? {
        name: android.latestVersionName,
        code: String(android.latestVersionCode),
        url: android.downloadUrl,
        message: android.message ?? "",
      }
    : { ...EMPTY_APP_VERSION_FORM };
}

/** Errori dei campi, con i testi mostrati sotto ciascun campo. Vuoto = si può salvare. */
export function validateAppVersionForm(fields: AppVersionFormFields): AppVersionFormErrors {
  const errors: AppVersionFormErrors = {};
  if (!VERSION_NAME_PATTERN.test(fields.name.trim())) {
    errors.name = "Scrivi la versione con numeri e punti, per esempio 1.3.0.";
  }
  const code = Number(fields.code.trim());
  if (!/^\d+$/.test(fields.code.trim()) || code < 1 || code > MAX_VERSION_CODE) {
    errors.code = "Il versionCode è un numero intero maggiore di zero.";
  }
  if (!isHttpsDownloadUrl(fields.url)) {
    errors.url = "Il link deve iniziare con https://";
  }
  if (fields.message.trim().length > MAX_MESSAGE_LENGTH) {
    errors.message = "Il messaggio può avere al massimo 200 caratteri.";
  }
  return errors;
}

/** Corpo di `PUT /admin/app-version` dai campi già validati. */
export function appVersionUpdateFrom(fields: AppVersionFormFields): AndroidAppVersionUpdate {
  return {
    latestVersionName: fields.name.trim(),
    latestVersionCode: Number(fields.code.trim()),
    downloadUrl: fields.url.trim(),
    message: fields.message.trim() || null,
  };
}
