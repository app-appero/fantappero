/**
 * Avviso «È disponibile la versione X dell'app» (pilota-1.2, Rosario 21/11): quando mostrarlo.
 *
 * Solo logica pura e import di tipo: gira nei test `node:test` senza il bundle di
 * `@fantappero/contracts`. Il confronto dei versionCode (`isNewerAppVersion`) arriva da
 * `@fantappero/contracts` e si passa come argomento.
 */
import type { AndroidAppVersion } from "@fantappero/contracts";

/** La versione pubblicata si richiede al più ogni 3 ore (avvio dopo l'accesso e ritorno in primo piano). */
export const APP_VERSION_REFRESH_MS = 3 * 60 * 60 * 1000;

export type UpdateBannerInput = {
  /** `Platform.OS`: l'avviso è solo per l'APK Android (il sito è sempre aggiornato). */
  platformOS: string;
  /** Accesso fatto e app utilizzabile (niente schermate di accesso, registrazione o richiesta). */
  signedIn: boolean;
  /** versionCode dell'app installata; `null` se non si legge. */
  installedVersionCode: number | null;
  /** Ultima versione pubblicata dal server; `null` se non impostata o non ancora letta. */
  latest: AndroidAppVersion | null;
  /** versionCode per cui si è toccato «Più tardi»; `null` se mai. */
  dismissedVersionCode: number | null;
};

export type VersionComparator = (
  installedCode: number | null | undefined,
  latestCode: number | null | undefined,
) => boolean;

/** La versione da annunciare, oppure `null` se l'avviso non va mostrato. */
export function updateBannerVersion(
  input: UpdateBannerInput,
  isNewer: VersionComparator,
): AndroidAppVersion | null {
  const { latest } = input;
  if (input.platformOS !== "android" || !input.signedIn || !latest) {
    return null;
  }
  if (!isNewer(input.installedVersionCode, latest.latestVersionCode)) {
    return null;
  }
  // «Più tardi» vale solo per quella versione: ne esce una più nuova e l'avviso torna.
  if (input.dismissedVersionCode !== null && latest.latestVersionCode <= input.dismissedVersionCode) {
    return null;
  }
  return latest;
}

/** Vero se la versione pubblicata va richiesta di nuovo al server. */
export function shouldRefreshAppVersion(
  lastFetchedAt: number | null,
  now: number,
  intervalMs: number = APP_VERSION_REFRESH_MS,
): boolean {
  return lastFetchedAt === null || now - lastFetchedAt >= intervalMs || now < lastFetchedAt;
}

/** versionCode salvato per «Più tardi»; un valore illeggibile vale «mai». */
export function parseDismissedVersionCode(stored: string | null | undefined): number | null {
  if (!stored || !/^\d+$/.test(stored.trim())) {
    return null;
  }
  const code = Number(stored.trim());
  return Number.isSafeInteger(code) && code > 0 ? code : null;
}
