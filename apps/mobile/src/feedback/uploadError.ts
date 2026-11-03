/**
 * Messaggio per l'utente quando l'invio di una segnalazione fallisce.
 *
 * Una richiesta che cade «a livello di rete» (nessuna risposta dal server) con un video allegato
 * è quasi sempre un caricamento troppo lento o interrotto sulla rete mobile: il messaggio
 * generico «Connessione non disponibile» non aiuta, questo dice cosa provare.
 */
export function feedbackUploadErrorMessage(error: unknown, options: { hasVideo: boolean }): string {
  const code = (error as { code?: unknown } | null)?.code;
  if (code === "network_error") {
    return options.hasVideo
      ? "Il caricamento non è arrivato al server. Un video pesa molto e la rete mobile può non bastare: riprova con il Wi‑Fi, oppure invia la segnalazione con la sola immagine."
      : "Connessione non disponibile. Controlla la rete e riprova.";
  }
  const message = (error as { message?: unknown } | null)?.message;
  return typeof message === "string" && message.trim() ? message : "Invio non riuscito. Riprova tra poco.";
}

/** Soglia oltre la quale conviene avvisare di usare il Wi‑Fi (somma dei pesi, in byte). */
export const LARGE_UPLOAD_BYTES = 8 * 1024 * 1024;

export function isLargeUpload(sizes: ReadonlyArray<number | null | undefined>): boolean {
  return sizes.reduce<number>((sum, size) => sum + (size ?? 0), 0) > LARGE_UPLOAD_BYTES;
}
