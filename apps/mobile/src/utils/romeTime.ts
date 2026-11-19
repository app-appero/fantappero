/**
 * Data e ora di un evento del server (es. apertura e chiusura di un'asta) sempre nell'ora
 * italiana, come nel resto dell'app. Prima l'asta a buste usava l'ora del telefono: su un
 * dispositivo in UTC mostrava un'ora indietro (QA emulatore 19/11, KO-D).
 */
export function formatRomeDateTime(value: string | Date | null | undefined): string {
  if (!value) {
    return "—";
  }
  const date = value instanceof Date ? value : new Date(value);
  if (Number.isNaN(date.getTime())) {
    return typeof value === "string" ? value : "—";
  }
  return new Intl.DateTimeFormat("it-IT", {
    dateStyle: "medium",
    timeStyle: "short",
    timeZone: "Europe/Rome",
  }).format(date);
}
