import assert from "node:assert/strict";
import test from "node:test";
import { feedbackUploadErrorMessage, isLargeUpload } from "./uploadError.ts";

test("una caduta di rete con un video suggerisce Wi‑Fi o la sola immagine", () => {
  const message = feedbackUploadErrorMessage({ code: "network_error", message: "Connessione non disponibile." }, { hasVideo: true });
  assert.match(message, /Wi‑Fi/);
  assert.match(message, /sola immagine/);
});

test("una caduta di rete senza video resta un messaggio semplice", () => {
  const message = feedbackUploadErrorMessage({ code: "network_error" }, { hasVideo: false });
  assert.equal(message, "Connessione non disponibile. Controlla la rete e riprova.");
});

test("gli errori del server mantengono il loro messaggio", () => {
  assert.equal(
    feedbackUploadErrorMessage({ code: "feedback_attachment_too_large", message: "Il file supera il peso massimo di 50 MB per i video." }, { hasVideo: true }),
    "Il file supera il peso massimo di 50 MB per i video.",
  );
});

test("senza messaggio usa quello generico", () => {
  assert.equal(feedbackUploadErrorMessage(null, { hasVideo: false }), "Invio non riuscito. Riprova tra poco.");
  assert.equal(feedbackUploadErrorMessage(new Error(" "), { hasVideo: false }), "Invio non riuscito. Riprova tra poco.");
});

test("avvisa solo oltre gli 8 MB totali e ignora i pesi sconosciuti", () => {
  assert.equal(isLargeUpload([705 * 1024, 12.8 * 1024 * 1024]), true);
  assert.equal(isLargeUpload([2 * 1024 * 1024, null, undefined]), false);
  assert.equal(isLargeUpload([]), false);
});
