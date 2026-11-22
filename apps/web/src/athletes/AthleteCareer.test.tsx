import type { AthleteCard, AthleteCareerRow } from "@fantappero/contracts";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { AthleteCardView } from "./AthleteCard";

/** Carriera nella scheda calciatore (1.3, canvas «Scheda calciatore»). */

function row(extra: Partial<AthleteCareerRow>): AthleteCareerRow {
  return {
    seasonYear: 2025,
    seasonLabel: "25/26",
    isCurrent: false,
    source: "provider",
    clubId: "lazio",
    clubName: "Lazio",
    competitionId: "serie-a",
    competitionName: "Serie A",
    appearances: 30,
    minutes: 2700,
    averageRating: 6.7,
    votes: null,
    fantasyAverage: null,
    goals: 10,
    assists: 4,
    goalsConceded: 30,
    saves: 80,
    penaltiesSaved: 1,
    yellowCards: 3,
    redCards: 0,
    cleanSheets: null,
    ...extra,
  };
}

const BASE: AthleteCard = {
  athleteId: "athlete-1",
  providerId: 7,
  canonicalName: "C. Rinaldi",
  firstName: "Carlo",
  lastName: "Rinaldi",
  nationality: "Italy",
  birthDate: "2001-09-02",
  age: 25,
  height: "189 cm",
  weight: null,
  injured: false,
  photoUrl: null,
  clubName: "Lazio",
  shirtNumber: 35,
  role: "P",
  effectiveRole: "P",
  providerPositionRaw: "Goalkeeper",
  assignment: null,
  seasons: [{ clubName: "Lazio", seasonYear: 2026, shirtNumber: 35, positionRaw: "Goalkeeper", isActive: true }],
  transfers: [],
  marketValue: 31,
  seasonAverage: { value: 6.4, seasonYear: 2026, seasonLabel: "26/27", isCurrent: true },
};

// Arrivano in disordine: la scheda le mette dalla più recente.
const GOALKEEPER_CAREER: AthleteCareerRow[] = [
  row({ seasonYear: 2024, seasonLabel: "24/25", appearances: 31, goalsConceded: 34, saves: 95, penaltiesSaved: 2, averageRating: 6.35 }),
  row({
    seasonYear: 2026,
    seasonLabel: "26/27",
    isCurrent: true,
    source: "fantappero",
    appearances: 12,
    goalsConceded: 11,
    cleanSheets: 5,
    penaltiesSaved: 1,
    saves: 38,
    averageRating: 6.4,
  }),
  row({
    seasonYear: 2025,
    seasonLabel: "25/26",
    clubId: null,
    clubName: "Bournemouth",
    competitionId: null,
    competitionName: "Premier League",
    appearances: 28,
    goalsConceded: 39,
    penaltiesSaved: 0,
    saves: 102,
    averageRating: 6.18,
  }),
];

function render(card: AthleteCard): HTMLElement {
  const host = document.createElement("div");
  host.innerHTML = renderToStaticMarkup(createElement(AthleteCardView, { card }));
  return host;
}

function headers(view: HTMLElement): string[] {
  return Array.from(view.querySelectorAll('[data-testid="athlete-career-table"] thead th')).map(
    (cell) => cell.textContent ?? "",
  );
}

function cells(view: HTMLElement, index: number): string[] {
  return Array.from(view.querySelectorAll(`[data-testid="athlete-career-row-${index}"] td`)).map(
    (cell) => cell.textContent ?? "",
  );
}

describe("carriera nella scheda calciatore (1.3)", () => {
  it("portiere: gol subiti, porte inviolate, rigori parati e parate; dalla stagione più recente", () => {
    const view = render({ ...BASE, career: GOALKEEPER_CAREER });
    expect(view.querySelector("h3")?.textContent ?? "").not.toBe("Stagioni");
    expect(view.textContent).toContain("Carriera");
    expect(headers(view)).toEqual([
      "Stagione",
      "Squadra",
      "Campionato",
      "Pres.",
      "Subiti",
      "Inviolate",
      "Rig. parati",
      "Parate",
      "Media",
    ]);
    expect(view.querySelector('[data-testid="athlete-career-table"] abbr[title="Porte inviolate"]')).not.toBeNull();
    // Stagione in corso per prima ed evidenziata, con le porte inviolate.
    expect(cells(view, 0)).toEqual(["2026/27 ● (in corso)", "Lazio", "Serie A", "12", "11", "5", "1", "38", "6,40"]);
    expect(view.querySelector('[data-testid="athlete-career-row-0"]')?.className).toContain("current");
    // Stagioni passate: porte inviolate non note → «—».
    expect(cells(view, 1)).toEqual(["2025/26", "Bournemouth", "Premier League", "28", "39", "—", "0", "102", "6,18"]);
    expect(cells(view, 2)[0]).toBe("2024/25");
    expect(cells(view, 2)[5]).toBe("—");
    // Niente gol e assist per il portiere.
    expect(headers(view)).not.toContain("Gol");
    expect(headers(view)).not.toContain("Assist");
  });

  it("le schede del telefono ripetono la stessa riga in parole", () => {
    const view = render({ ...BASE, career: GOALKEEPER_CAREER });
    const cards = Array.from(view.querySelectorAll(".fa-athlete-career__card"));
    expect(cards).toHaveLength(3);
    expect(cards[0]?.className).toContain("fa-athlete-career__card--current");
    expect(cards[0]?.textContent).toContain("2026/27 · Lazio");
    expect(cards[0]?.textContent).toContain("12 pres. · 11 subiti · 5 inviolate · 1 rig. parati · 38 parate · 6,40 media");
  });

  it("giocatore di movimento: presenze, gol, assist e media voto", () => {
    const view = render({
      ...BASE,
      role: "A",
      effectiveRole: "A",
      career: [row({ seasonYear: 2026, seasonLabel: "26/27", isCurrent: true, appearances: 11, goals: 6, assists: 2, averageRating: 6.85 })],
    });
    expect(headers(view)).toEqual(["Stagione", "Squadra", "Campionato", "Pres.", "Gol", "Assist", "Media"]);
    expect(cells(view, 0)).toEqual(["2026/27 ● (in corso)", "Lazio", "Serie A", "11", "6", "2", "6,85"]);
  });

  it("«Valore N» sotto il club; carriera vuota con un messaggio", () => {
    const view = render({ ...BASE, career: [] });
    expect(view.querySelector(".fa-athlete-card__hero .fa-market-value")?.textContent).toBe("Valore 31");
    expect(view.textContent).toContain("Nessuna stagione nello storico.");
  });

  it("backend senza `career`: resta l'elenco «Stagioni» di prima", () => {
    const old: AthleteCard = { ...BASE };
    delete old.marketValue;
    expect("career" in old).toBe(false);
    const view = render(old);
    expect(view.textContent).toContain("Stagioni");
    expect(view.textContent).toContain("2026 · Lazio");
    expect(view.querySelector('[data-testid="athlete-career"]')).toBeNull();
    expect(view.querySelector(".fa-market-value")).toBeNull();
  });
});
