import type { NotificationItem } from "@fantappero/contracts";

export type NotificationGroup = "giocatori" | "scambi" | "asta" | "formazione" | "turni" | "sistema";

export type NotificationKind = { group: NotificationGroup; glyph: string };

export const NOTIFICATION_GROUP_LABEL: Record<NotificationGroup, string> = {
  giocatori: "Giocatori",
  scambi: "Scambi",
  asta: "Asta",
  formazione: "Formazione",
  turni: "Turni",
  sistema: "Sistema",
};

/** Colore (testo/icona) e fondo di ogni gruppo, come nel mockup. */
export const NOTIFICATION_GROUP_COLOR: Record<NotificationGroup, { fg: string; bg: string }> = {
  giocatori: { fg: "#FF6B8A", bg: "rgba(255,107,138,0.18)" },
  scambi: { fg: "#7DD3FC", bg: "rgba(56,189,248,0.18)" },
  asta: { fg: "#FFD23F", bg: "rgba(255,210,63,0.18)" },
  formazione: { fg: "#34D399", bg: "rgba(52,211,153,0.18)" },
  turni: { fg: "#B58CFF", bg: "rgba(181,140,255,0.18)" },
  sistema: { fg: "#9DB8FF", bg: "rgba(157,184,255,0.18)" },
};

/** Gruppo e icona di una notifica, ricavati dal titolo (i modelli sono versionati nel backend). */
export function notificationKind(item: Pick<NotificationItem, "title" | "category">): NotificationKind {
  const title = item.title.toLowerCase();
  if (title.startsWith("gol")) return { group: "giocatori", glyph: "⚽" };
  if (title.startsWith("assist")) return { group: "giocatori", glyph: "🅰" };
  if (title.startsWith("ammonito")) return { group: "giocatori", glyph: "🟨" };
  if (title.startsWith("espuls")) return { group: "giocatori", glyph: "🟥" };
  if (title.startsWith("infortunio") || title.includes("infortunato")) return { group: "giocatori", glyph: "🩹" };
  if (title.includes("squalific")) return { group: "giocatori", glyph: "⛔" };
  if (title.startsWith("esce ")) return { group: "giocatori", glyph: "🔁" };
  if (title.includes("scambio") || title.includes("controproposta")) {
    return { group: "scambi", glyph: title.includes("proposta") || title.includes("propone") ? "⇄" : "✓" };
  }
  if (title.includes("sorpassato")) return { group: "asta", glyph: "🔨" };
  if (title.includes("busta") || title.includes("lotto") || title.includes("asta") || title.includes("rosa al completo")) {
    return { group: "asta", glyph: "🔨" };
  }
  if (title.includes("formazione")) return { group: "formazione", glyph: "⏰" };
  if (title.includes("omologat")) return { group: "turni", glyph: "🏁" };
  if (title.includes("invito")) return { group: "sistema", glyph: "✉" };
  if (item.category === "risultati") return { group: "turni", glyph: "🏁" };
  if (item.category === "mercato") return { group: "scambi", glyph: "⇄" };
  if (item.category === "formazione") return { group: "formazione", glyph: "⏰" };
  return { group: "sistema", glyph: "🔔" };
}

/** «Oggi», «Ieri» o la data estesa, per raggruppare l'elenco. */
export function notificationDayLabel(iso: string, now: Date = new Date()): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "Altre";
  const startOf = (value: Date) => new Date(value.getFullYear(), value.getMonth(), value.getDate()).getTime();
  const diffDays = Math.round((startOf(now) - startOf(date)) / 86_400_000);
  if (diffDays === 0) return "Oggi";
  if (diffDays === 1) return "Ieri";
  return date.toLocaleDateString("it-IT", { day: "numeric", month: "long" });
}
