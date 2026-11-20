import type { RosterImportPreview } from "@fantappero/contracts";
import { canConfirmRosterImport } from "@fantappero/contracts";
import { createElement, createRef } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { RosterCsvImportCard } from "./RosterCsvImportCard";

// QA 19-20/11: "toni fernandez" finiva in silenzio su uno dei due Toni Fernández.
// Ora la riga è ambigua e per scegliere servono ruolo, squadra e campionato.
const preview: RosterImportPreview = {
  importId: "import-1",
  status: "draft",
  fileSha256: "sha",
  originalFilename: "rosa.xlsx",
  canConfirm: false,
  rowCount: 2,
  errorCount: 0,
  ambiguousCount: 1,
  warningCount: 1,
  confirmedAt: null,
  rows: [
    {
      rowNumber: 2,
      squadra: "Squadra",
      providerId: 10,
      nome: "Barella",
      crediti: 10,
      status: "ok",
      fantasyTeamId: "team-1",
      fantasyTeamName: "Squadra",
      athleteId: "barella",
      athleteName: "N. Barella",
      slotIndex: 0,
      issues: [],
      candidates: [],
    },
    {
      rowNumber: 3,
      squadra: "Squadra",
      providerId: null,
      nome: "toni fernandez",
      crediti: 3,
      status: "ambiguous",
      fantasyTeamId: "team-1",
      fantasyTeamName: "Squadra",
      athleteId: null,
      athleteName: null,
      slotIndex: null,
      issues: [
        {
          code: "ambiguous_athlete_name",
          message: "Nome ambiguo: seleziona il calciatore corretto.",
          severity: "warning",
        },
      ],
      candidates: [
        {
          athleteId: "barca",
          providerId: 1,
          canonicalName: "Toni Fernández",
          role: "C",
          clubName: "Barcelona",
          competitionName: "La Liga",
        },
        {
          athleteId: "venezia",
          providerId: 2,
          canonicalName: "Toni Fernández",
          role: "A",
          clubName: "Venezia",
          competitionName: "Serie B",
        },
      ],
    },
  ],
};

function render(resolutions: Record<number, string>) {
  return renderToStaticMarkup(
    createElement(RosterCsvImportCard, {
      csvBusy: false,
      adminTeamName: "Squadra",
      onDownloadCsvTemplate: () => undefined,
      onDownloadRosterExport: () => undefined,
      onDownloadAllRostersExport: () => undefined,
      csvFileInputRef: createRef<HTMLInputElement>(),
      onCsvFileSelected: () => undefined,
      bulkCsvFileInputRef: createRef<HTMLInputElement>(),
      onBulkCsvFileSelected: () => undefined,
      csvCanConfirm: canConfirmRosterImport(preview, resolutions),
      onConfirmCsvImport: () => undefined,
      csvMessage: null,
      csvError: null,
      csvPreview: preview,
      csvResolutions: resolutions,
      onCsvResolutionChange: () => undefined,
    }),
  );
}

describe("RosterCsvImportCard: omonimi", () => {
  it("shows role, club and competition of each candidate", () => {
    const html = render({});
    expect(html).toContain('data-testid="roster-excel-resolve-3"');
    expect(html).toContain("Toni Fernández — Centrocampista · Barcelona · La Liga");
    expect(html).toContain("Toni Fernández — Attaccante · Venezia · Serie B");
  });

  it("counts ambiguous names apart from errors", () => {
    const html = render({});
    expect(html).toContain("errori 0 · nomi ambigui 1 · avvisi");
    expect(html).toContain('data-testid="roster-excel-ambiguous-hint"');
    expect(html).toContain("scegli quello giusto (ruolo e squadra)");
  });

  it("enables the confirmation only after choosing the candidate", () => {
    const blocked = render({});
    expect(blocked).toMatch(/<button[^>]*disabled=""[^>]*data-testid="roster-excel-confirm"/);
    const chosen = render({ 3: "venezia" });
    expect(chosen).not.toMatch(/<button[^>]*disabled=""[^>]*data-testid="roster-excel-confirm"/);
  });
});
