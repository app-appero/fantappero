import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import {
  AuthFormLayout,
  AuctionBidPanel,
  BrandLogo,
  StandingsTable,
  WireframeSection,
} from "../index.js";

describe("EPUI-04 domain wireframe components", () => {
  it("renders wireframe section with region label", () => {
    const html = renderToStaticMarkup(
      createElement(WireframeSection, { label: "Regione demo" }, "Contenuto"),
    );
    expect(html).toContain('data-wireframe-region="Regione demo"');
  });

  it("renders standings table with current user row", () => {
    const html = renderToStaticMarkup(
      createElement(StandingsTable, {
        caption: "Classifica",
        positionLabel: "Pos.",
        teamLabel: "Squadra",
        playedLabel: "G",
        pointsLabel: "Pt",
        goalsLabel: "GF:GS",
        rows: [
          {
            id: "1",
            position: 1,
            teamName: "Tu",
            played: 1,
            points: 3,
            goalsFor: 70,
            goalsAgainst: 60,
            isCurrentUser: true,
            highlightLabel: "Tu",
          },
        ],
      }),
    );
    expect(html).toContain('data-testid="standings-table"');
    expect(html).toContain('data-testid="standings-row-current"');
  });

  it("renders auction bid panel", () => {
    const html = renderToStaticMarkup(
      createElement(AuctionBidPanel, {
        title: "Offerta",
        budgetLabel: "Budget",
        budgetValue: "100",
        playerLabel: "Giocatore",
        playerPlaceholder: "Cerca",
        bidLabel: "Offerta",
        bidPlaceholder: "0",
        submitLabel: "Invia",
        statusLabel: "Stato",
        statusMessage: "Aperta",
      }),
    );
    expect(html).toContain('data-testid="auction-bid-panel"');
  });

  it("renders auth form layout", () => {
    const html = renderToStaticMarkup(
      createElement(AuthFormLayout, {
        brand: createElement(BrandLogo, { variant: "full" }),
        title: "Accedi",
        emailLabel: "Email",
        emailPlaceholder: "a@b.it",
        passwordLabel: "Password",
        passwordPlaceholder: "***",
        submitLabel: "Accedi",
      }),
    );
    expect(html).toContain('data-testid="auth-form-layout"');
    expect(html).toContain('data-testid="brand-logo"');
    expect(html).toContain("FantApperò");
  });

  it("renders brand logo mark and full variants", () => {
    const markHtml = renderToStaticMarkup(createElement(BrandLogo, { variant: "mark" }));
    expect(markHtml).toContain('data-testid="brand-logo"');
    expect(markHtml).not.toContain("FantApperò");

    const fullHtml = renderToStaticMarkup(createElement(BrandLogo, { variant: "full" }));
    expect(fullHtml).toContain("FantApperò");
  });
});
