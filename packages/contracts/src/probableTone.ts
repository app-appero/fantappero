/** Stato di un calciatore dalle formazioni probabili: stessa regola su web e app. */
export type ProbableTone = "starter" | "bench" | "expelled" | "unavailable";

export function probableToneOf(row: {
  probableHint?: "starter" | "bench" | "unavailable" | null;
  probableAbsence?: "suspended" | "injured" | "other" | null;
  selectionBlocked?: boolean;
}): ProbableTone | null {
  if (row.probableHint === "unavailable" || row.selectionBlocked) {
    return row.probableAbsence === "suspended" ? "expelled" : "unavailable";
  }
  if (row.probableHint === "starter") return "starter";
  if (row.probableHint === "bench") return "bench";
  return null;
}
