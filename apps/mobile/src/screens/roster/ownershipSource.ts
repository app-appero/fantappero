import type { RosterOwnershipSource } from "@fantappero/contracts";

const OWNERSHIP_SOURCE_LABEL: Record<RosterOwnershipSource, string> = {
  manual: "Inserimento manuale",
  csv_import: "Importazione da file",
  admin: "Assegnazione admin",
  market: "Mercato",
};

/**
 * Etichetta italiana dell'origine di un possesso nello storico della rosa (codice backend
 * `RosterOwnershipSource`; QA 19-20/11: si vedeva il codice, «market» o «csv_import»). Un codice
 * nuovo non ancora tradotto mostra «Altro». Stesse etichette del web (`rosterHelpers.ts`).
 */
export function ownershipSourceLabel(source: string): string {
  return Object.prototype.hasOwnProperty.call(OWNERSHIP_SOURCE_LABEL, source)
    ? OWNERSHIP_SOURCE_LABEL[source as RosterOwnershipSource]
    : "Altro";
}
