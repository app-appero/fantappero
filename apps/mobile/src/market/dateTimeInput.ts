/**
 * Parses a `YYYY-MM-DD HH:mm` (or `YYYY-MM-DDTHH:mm`) text field into an ISO datetime string,
 * mirroring what the web `<input type="datetime-local">` produces before `.toISOString()`.
 * Returns null when the text does not represent a valid date.
 */
export function parseLocalDateTimeInput(value: string): string | null {
  const trimmed = value.trim();
  if (!trimmed) {
    return null;
  }
  const normalized = trimmed.includes("T") ? trimmed : trimmed.replace(" ", "T");
  const parsed = new Date(normalized);
  if (Number.isNaN(parsed.getTime())) {
    return null;
  }
  return parsed.toISOString();
}
