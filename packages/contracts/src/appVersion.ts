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
