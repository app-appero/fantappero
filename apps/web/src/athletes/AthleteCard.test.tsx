import type { AthleteCard } from "@fantappero/contracts";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { AthleteCardView, AthleteName } from "./AthleteCard";

const CARD: AthleteCard = {
  athleteId: "athlete-1",
  providerId: 42,
  canonicalName: "K. Thuram",
  firstName: "Khéphren",
  lastName: "Thuram",
  nationality: "France",
  birthDate: "2001-03-26",
  age: 25,
  height: "192 cm",
  weight: "78 kg",
  injured: false,
  photoUrl: "https://example.test/thuram.png",
  clubName: "Nice",
  shirtNumber: 19,
  role: "C",
  effectiveRole: "C",
  providerPositionRaw: "Midfielder",
  assignment: {
    fantasyTeamId: "team-1",
    teamName: "Rosa Nord",
    slotIndex: 0,
    purchaseCredits: 22,
  },
  seasons: [
    {
      clubName: "Nice",
      seasonYear: 2099,
      shirtNumber: 19,
      positionRaw: "Midfielder",
      isActive: true,
    },
  ],
  transfers: [
    {
      transferDate: "2024-07-01",
      fromClubName: "Lille",
      toClubName: "Nice",
      transferType: "Loan",
    },
  ],
};

describe("AthleteCardView", () => {
  it("mostra foto, anagrafica, stagione, trasferimento e squadra di lega", () => {
    const html = renderToStaticMarkup(createElement(AthleteCardView, { card: CARD }));
    expect(html).toContain("https://example.test/thuram.png");
    expect(html).toContain("Khéphren Thuram");
    expect(html).toContain("Nice");
    expect(html).toContain("France");
    expect(html).toContain("26/03/2001");
    expect(html).toContain("Rosa Nord");
    expect(html).toContain("22 crediti");
    expect(html).toContain("2099");
    expect(html).toContain("Lille");
    expect(html).toContain("Prestito");
    expect(html).toContain("Disponibile");
  });

  it("indica Libero quando nessuno ha il calciatore in rosa", () => {
    const html = renderToStaticMarkup(
      createElement(AthleteCardView, { card: { ...CARD, assignment: null, photoUrl: null } }),
    );
    expect(html).toContain("Libero");
    expect(html).toContain("KT");
  });
});

describe("AthleteName", () => {
  it("resta testo quando la scheda non è montata", () => {
    const html = renderToStaticMarkup(
      createElement(AthleteName, { athleteId: "athlete-1", children: "K. Thuram" }),
    );
    expect(html).toContain("K. Thuram");
    expect(html).not.toContain("<button");
  });
});
