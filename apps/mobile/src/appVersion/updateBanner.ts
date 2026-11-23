/**
 * Avviso «È disponibile la versione X dell'app»: quando mostrarlo.
 *
 * Pilota-1.2 (Rosario 21/11): l'avviso con «Scarica» e «Più tardi». Release 1.4 (Rosario 23/11):
 * si propone a ogni ingresso nell'app finché non è aggiornata. La versione si chiede a ogni avvio
 * e a ogni ritorno in primo piano (al più una volta al minuto, contro i giri a vuoto); «Più tardi»
 * lo nasconde solo fino al prossimo avvio o ritorno in primo piano.
 *
 * Solo logica pura e import di tipo: gira nei test `node:test` senza il bundle di
 * `@fantappero/contracts`. Il confronto dei versionCode (`isNewerAppVersion`) arriva da
 * `@fantappero/contracts` e si passa come argomento.
 */
import type { AndroidAppVersion } from "@fantappero/contracts";

/** Fra due richieste della versione almeno un minuto (avvio e ritorni in primo piano ravvicinati). */
export const APP_VERSION_MIN_INTERVAL_MS = 60 * 1000;

export type UpdateBannerInput = {
  /** `Platform.OS`: l'avviso è solo per l'APK Android (il sito è sempre aggiornato). */
  platformOS: string;
  /** Accesso fatto e app utilizzabile (niente schermate di accesso, registrazione o richiesta). */
  signedIn: boolean;
  /** versionCode dell'app installata; `null` se non si legge. */
  installedVersionCode: number | null;
  /** Ultima versione pubblicata dal server; `null` se non impostata o non ancora letta. */
  latest: AndroidAppVersion | null;
  /**
   * versionCode per cui si è toccato «Più tardi» da quando l'app è in primo piano; `null` se
   * no. Non si salva: al prossimo avvio o ritorno in primo piano l'avviso torna.
   */
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
  // «Più tardi» vale per quella versione e solo finché l'app resta in primo piano.
  if (input.dismissedVersionCode !== null && latest.latestVersionCode <= input.dismissedVersionCode) {
    return null;
  }
  return latest;
}

/** Vero se la versione pubblicata va richiesta di nuovo al server (avvio o primo piano). */
export function shouldRefreshAppVersion(
  lastFetchedAt: number | null,
  now: number,
  intervalMs: number = APP_VERSION_MIN_INTERVAL_MS,
): boolean {
  return lastFetchedAt === null || now - lastFetchedAt >= intervalMs || now < lastFetchedAt;
}

/**
 * Vero se il cambio di stato dell'app è un «ritorno in primo piano» (dallo sfondo), cioè un
 * nuovo ingresso nell'app: si richiede la versione e il «Più tardi» non vale più.
 */
export function isReturnToForeground(previous: string | null | undefined, next: string): boolean {
  return next === "active" && (previous === "background" || previous === "inactive");
}
