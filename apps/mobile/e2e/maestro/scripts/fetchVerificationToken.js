// Recupera il token di verifica email dalla API REST di Mailpit (v1.22, vedi
// compose.yaml), riusando la stessa tecnica di apps/e2e/helpers/mailpit.ts
// (waitForVerificationLink), adattata per estrarre solo il token e per
// l'ambiente JS di Maestro invece che Node/Playwright.
//
// NOTA (non ancora verificato contro l'installazione reale di Maestro):
// questo script assume che l'ambiente `runScript` esponga un oggetto globale
// `http` con `http.get(url)` che restituisce `{ ok, body }` (`body` già
// parsato se JSON, o stringa altrimenti) e un oggetto `output` su cui
// scrivere variabili leggibili dal flow YAML come `${output.<chiave>}`. La
// sintassi esatta va confermata contro la versione di Maestro CLI installata
// prima del primo giro di prova.

const email = MAESTRO_TEST_EMAIL;
const mailpitBaseUrl = MAESTRO_MAILPIT_BASE_URL || "http://10.0.2.2:8025";

const verificationLinkPattern = /https?:\/\/\S+\/accedi\/verifica\?token=([^\s&"]+)/;

function findLatestMessageId(recipientEmail) {
  const list = http.get(`${mailpitBaseUrl}/api/v1/messages?limit=50`);
  const messages = (list.body && list.body.messages) || [];
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
  const detail = http.get(`${mailpitBaseUrl}/api/v1/message/${messageId}`);
  const body = (detail.body && (detail.body.Text || detail.body.HTML)) || "";
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
