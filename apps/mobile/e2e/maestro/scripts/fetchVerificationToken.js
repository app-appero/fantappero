// Recupera il token di verifica email dalla API REST di Mailpit (v1.22, vedi
// compose.yaml), riusando la stessa tecnica di apps/e2e/helpers/mailpit.ts
// (waitForVerificationLink), adattata per estrarre solo il token e per
// l'ambiente JS di Maestro invece che Node/Playwright.
//
// VERIFICATO nel dry run (26/09/2026) su Maestro 2.10.0: `http.get(url)`
// restituisce `{ ok, status, body }` dove `body` è la stringa grezza della
// risposta (JSON compreso) — va sempre passata a `JSON.parse`, non è già un
// oggetto. Prima di questo fix lo script cercava `.messages` direttamente
// su una stringa (sempre `undefined`), quindi non trovava mai nulla anche
// con l'email realmente arrivata in Mailpit.

const email = MAESTRO_TEST_EMAIL;
const mailpitBaseUrl = MAESTRO_MAILPIT_BASE_URL || "http://10.0.2.2:8025";

const verificationLinkPattern = /https?:\/\/\S+\/accedi\/verifica\?token=([^\s&"]+)/;

function findLatestMessageId(recipientEmail) {
  const list = JSON.parse(http.get(`${mailpitBaseUrl}/api/v1/messages?limit=50`).body);
  const messages = list.messages || [];
  const matches = messages
    .filter((message) =>
      (message.To || []).some(
        (to) => String(to.Address).toLowerCase() === recipientEmail.toLowerCase(),
      ),
    )
    .sort((a, b) => new Date(b.Created).getTime() - new Date(a.Created).getTime());
  return matches.length > 0 ? matches[0].ID : null;
}

function extractTokenFromMessage(messageId) {
  const detail = JSON.parse(http.get(`${mailpitBaseUrl}/api/v1/message/${messageId}`).body);
  const body = detail.Text || detail.HTML || "";
  const match = body.match(verificationLinkPattern);
  return match ? match[1] : null;
}

const timeoutMs = 15000;
const intervalMs = 500;
const deadline = Date.now() + timeoutMs;
let token = null;

while (Date.now() < deadline && !token) {
  const messageId = findLatestMessageId(email);
  if (messageId) {
    token = extractTokenFromMessage(messageId);
  }
  if (!token) {
    // Maestro esegue questo script in modo sincrono: un ciclo di attesa
    // busy-wait è l'unica opzione senza un vero `sleep` asincrono disponibile
    // nell'ambiente JS del runner. Da confermare se esiste un'alternativa
    // migliore nella versione installata.
    const wakeAt = Date.now() + intervalMs;
    while (Date.now() < wakeAt) {
      // no-op
    }
  }
}

if (!token) {
  throw new Error(`Nessun token di verifica trovato per ${email} entro ${timeoutMs}ms`);
}

output.verificationToken = token;
