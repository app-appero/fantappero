/**
 * Minimal client for the Mailpit REST API (v1.22, see compose.yaml) used to
 * retrieve verification/reset links sent by the real SMTP flow during E2E
 * runs — the backend's in-memory `mail.capture` used by pytest is not
 * reachable from outside the API process.
 */

const mailpitBaseURL = process.env.E2E_MAILPIT_BASE_URL ?? "http://localhost:8025";

interface MailpitMessageSummary {
  ID: string;
  To: { Address: string }[];
  Created: string;
}

interface MailpitMessagesResponse {
  messages: MailpitMessageSummary[];
}

interface MailpitMessageDetail {
  Text: string;
  HTML: string;
}

async function fetchJson<T>(url: string): Promise<T> {
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`Mailpit request failed: ${response.status} ${url}`);
  }
  return (await response.json()) as T;
}

async function latestMessageBodyFor(recipientEmail: string): Promise<string> {
  const list = await fetchJson<MailpitMessagesResponse>(
    `${mailpitBaseURL}/api/v1/messages?limit=50`,
  );
  const match = list.messages
    .filter((message) =>
      message.To.some((to) => to.Address.toLowerCase() === recipientEmail.toLowerCase()),
    )
    .sort((a, b) => new Date(b.Created).getTime() - new Date(a.Created).getTime())[0];
  if (!match) {
    throw new Error(`No Mailpit message found for ${recipientEmail}`);
  }
  const detail = await fetchJson<MailpitMessageDetail>(
    `${mailpitBaseURL}/api/v1/message/${match.ID}`,
  );
  return detail.Text || detail.HTML;
}

/** Polls Mailpit until an email to `recipientEmail` matching `linkPattern` arrives, then returns the first captured link. */
export async function waitForEmailLink(
  recipientEmail: string,
  linkPattern: RegExp,
  { timeoutMs = 15_000, intervalMs = 500 }: { timeoutMs?: number; intervalMs?: number } = {},
): Promise<string> {
  const deadline = Date.now() + timeoutMs;
  let lastError: unknown;
  while (Date.now() < deadline) {
    try {
      const body = await latestMessageBodyFor(recipientEmail);
      const match = body.match(linkPattern);
      if (match) {
        return match[0];
      }
    } catch (error) {
      lastError = error;
    }
    await new Promise((resolve) => setTimeout(resolve, intervalMs));
  }
  throw new Error(
    `Timed out waiting for an email link matching ${linkPattern} for ${recipientEmail}` +
      (lastError ? ` (last error: ${String(lastError)})` : ""),
  );
}

/** Convenience wrapper for the account verification link sent on registration. */
export async function waitForVerificationLink(recipientEmail: string): Promise<string> {
  return waitForEmailLink(recipientEmail, /https?:\/\/\S+\/accedi\/verifica\?token=\S+/);
}
