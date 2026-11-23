import type { FantasyRole, FantasyTeam } from "@fantappero/contracts";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import stylesCss from "../../styles.css?raw";
import { DEMO_TEAM } from "./rosterDemoData";
import { RosterFilledSummary } from "./RosterFilledSummary";

type RosterSlot = FantasyTeam["slots"][number];

const pendingDefender: RosterSlot = {
  id: "slot-4",
  slotIndex: 3,
  athleteId: "valou",
  athleteName: "J. Valou",
  photoUrl: null,
  clubName: "Udinese",
  role: "D",
  purchaseCredits: 1,
  exceedsRoleQuota: true,
};

function renderSummary(): string {
  const filledByRole: Record<FantasyRole | "unknown", RosterSlot[]> = {
    P: [],
    D: [pendingDefender],
    C: [],
    A: [],
    unknown: [],
  };
  return renderToStaticMarkup(
    createElement(RosterFilledSummary, {
      viewedTeam: DEMO_TEAM,
      filledByRole,
      canEdit: true,
      adminBusy: false,
      onReleaseAthlete: () => undefined,
    }),
  );
}

/** Il corpo del blocco `@container fa-roster-table (...)` di styles.css. */
function rosterContainerBlock(): { query: string; body: string } {
  const start = stylesCss.indexOf("@container fa-roster-table");
  expect(start, "manca la container query delle tabelle della Rosa").toBeGreaterThanOrEqual(0);
  const open = stylesCss.indexOf("{", start);
  let depth = 0;
  for (let index = open; index < stylesCss.length; index += 1) {
    if (stylesCss[index] === "{") {
      depth += 1;
    } else if (stylesCss[index] === "}") {
      depth -= 1;
      if (depth === 0) {
        return { query: stylesCss.slice(start, open), body: stylesCss.slice(open + 1, index) };
      }
    }
  }
  throw new Error("blocco @container non chiuso");
}

describe("Rosa: nome e badge «In esubero» in colonna stretta (QA 20-21/11, WEB-1)", () => {
  it("mette nome e badge nello stesso blocco che va a capo", () => {
    const html = renderSummary();
    const text = /<span class="fa-auction-player__text">([\s\S]*?)<\/span><\/span><\/td>/.exec(html);
    expect(text, html).not.toBeNull();
    expect(text?.[1]).toContain("J. Valou");
    expect(text?.[1]).toContain('class="fa-badge fa-badge--warning fa-auction-player__badge"');
    expect(text?.[1]).toContain("In esubero");
  });

  it("il badge del giocatore in esubero si legge «In esubero», non più «In attesa» (Rosario, 23/11)", () => {
    const html = renderSummary();
    const badge = /data-testid="roster-pending-badge-valou"[^>]*>([^<]*)</.exec(html)?.[1];
    expect(badge, html).toBe("In esubero");
    expect(html).not.toContain("In attesa");
  });

  it("accanto a «In esubero» c'è il «?» che apre la risposta sull'esubero (FAQ 1.4)", () => {
    const html = renderSummary();
    const pending = /<span class="fa-faq-help-inline">([\s\S]*?)<\/button><\/span>/.exec(html)?.[1] ?? "";
    expect(pending).toContain("In esubero");
    expect(pending).toContain('data-testid="roster-pending-help-valou"');
    expect(pending).toContain('aria-label="Ho un giocatore in esubero: cosa faccio?"');
    // Solo chi è in esubero ha il «?».
    expect(html.match(/class="fa-faq-help"/g)).toHaveLength(1);
  });

  it("il blocco va a capo e il badge non schiaccia il nome", () => {
    expect(stylesCss).toMatch(/\.fa-auction-player__text \{[^}]*flex-wrap: wrap;[^}]*min-width: 0;/);
    expect(stylesCss).toMatch(/\.fa-auction-player__badge \{[^}]*flex-shrink: 0;[^}]*max-width: 100%;/);
  });
});

describe("Rosa › Storico a 390 px: «Al» e «Fonte» raggiungibili (QA 22→23/11)", () => {
  it("la colonna della pagina non si allarga quanto la tabella più larga", () => {
    // Senza questa regola la griglia del corpo della pagina ha una colonna «auto» larga quanto
    // la tabella «Intervalli di possesso» (611 px con lo schermo a 374 px): la card usciva dallo
    // schermo invece di far scorrere la tabella nel suo riquadro. Stessa cura di Listone e Turni.
    expect(stylesCss).toMatch(
      /(?:^|\n)\.fa-roster-page > \.fa-page-container__body \{\s*grid-template-columns: minmax\(0, 1fr\);\s*\}/,
    );
  });
});

describe("Rosa: tabelle dei ruoli senza scorrimento a 1280 px (QA 20-21/11, WEB-2)", () => {
  it("le tabelle della Rosa sono container e diventano compatte quando sono strette", () => {
    expect(stylesCss).toMatch(
      /\.fa-roster-columns \.fa-table-wrap:has\(> \.fa-roster-table\) \{\s*container: fa-roster-table \/ inline-size;/,
    );
    const { query, body } = rosterContainerBlock();
    // A 1280 px la colonna dei ruoli è larga circa 370 px (23rem): deve essere compatta.
    const threshold = Number(/max-width: ([\d.]+)rem/.exec(query)?.[1]);
    expect(threshold).toBeGreaterThanOrEqual(32);
    expect(body).toMatch(/\.fa-roster-table \{\s*table-layout: fixed;/);
    // «Slot» e «Rimuovi» restano in tabella: colonna stretta e pulsante a icona.
    expect(body).toMatch(/\.fa-roster-col--slot \{\s*width: 1\.5rem;/);
    expect(body).toMatch(/\.fa-roster-action__label \{\s*position: absolute;/);
    expect(body).toMatch(/\.fa-roster-action__icon \{\s*display: inline-flex;/);
    expect(body).toMatch(/\.fa-roster-col-label--short \{\s*display: inline;/);
  });
});
