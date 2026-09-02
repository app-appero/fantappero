import type { FantasyCoachProfile } from "@fantappero/contracts";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { CoachProfilePanel } from "./ManagerDirectory";

function profile(overrides: Partial<FantasyCoachProfile> = {}): FantasyCoachProfile {
  return {
    userId: "coach-1",
    displayName: "Lucia Bianchi",
    avatarUrl: null,
    userType: "human",
    availableForInvites: true,
    namedInviteStatus: null,
    memberSince: "03/2025",
    concludedLeagues: 2,
    bestPosition: 1,
    historySummary: "2 leghe concluse · miglior 1º",
    placements: [
      {
        seasonYear: 2026,
        position: 1,
        participantCount: 8,
        played: 14,
        points: 30,
        fantasyPoints: 812.5,
      },
      {
        seasonYear: 2025,
        position: 4,
        participantCount: 6,
        played: 10,
        points: 15,
        fantasyPoints: 640,
      },
    ],
    placementsPage: 1,
    placementsPageSize: 20,
    placementsTotal: 2,
    ...overrides,
  };
}

function render(value: FantasyCoachProfile): string {
  return renderToStaticMarkup(
    createElement(CoachProfilePanel, { profile: value, onClose: () => {} }),
  );
}

describe("CoachProfilePanel — profilo storico limitato (EP13-P06)", () => {
  it("mostra nome, anzianità e riepilogo", () => {
    const html = render(profile());
    expect(html).toContain('data-testid="coach-profile"');
    expect(html).toContain("Lucia Bianchi");
    expect(html).toContain("iscritto da 03/2025");
    expect(html).toContain("2 leghe concluse · miglior 1º");
  });

  it("mostra i piazzamenti con il numero di partecipanti", () => {
    const html = render(profile());
    expect(html).toContain('data-testid="coach-profile-placements"');
    // Un 4º su 6 non vale un 4º su 20: il denominatore va mostrato.
    expect(html).toContain("4º su 6");
    expect(html).toContain("1º su 8");
  });

  it("mostra i fantapunti (magic) accanto ai punti classifica (esito)", () => {
    const html = render(profile());
    expect(html).toContain("Fantapunti");
    expect(html).toContain("812,5");
    expect(html).toContain("640,0");
  });

  it("non espone mai nomi di lega", () => {
    const html = render(profile());
    expect(html).not.toContain("leagueId");
    expect(html).not.toContain("Lega ");
    expect(html).toContain("I nomi delle leghe non sono visibili");
  });

  it("rende neutro un fantallenatore senza storico", () => {
    const html = render(
      profile({
        concludedLeagues: 0,
        bestPosition: null,
        historySummary: "Nessuna lega conclusa",
        placements: [],
        placementsTotal: 0,
      }),
    );
    expect(html).toContain('data-testid="coach-profile-empty"');
    expect(html).toContain("non ha ancora uno storico");
    expect(html).not.toContain('data-testid="coach-profile-placements"');
  });

  it("omette l'anzianità quando non è nota, senza inventarla", () => {
    const html = render(profile({ memberSince: null }));
    expect(html).not.toContain("iscritto da");
    expect(html).toContain("Lucia Bianchi");
  });

  it("distingue un fantallenatore IA da uno manuale", () => {
    expect(render(profile({ userType: "ai" }))).toContain("IA");
    expect(render(profile())).toContain("Manuale");
  });

  it("segnala chi non è disponibile agli inviti", () => {
    expect(render(profile({ availableForInvites: false }))).toContain("Non disponibile");
  });
});
