import type { LeagueListoneEntry } from "@fantappero/contracts";
import { act, createElement } from "react";
import { createRoot, type Root } from "react-dom/client";
import { renderToStaticMarkup } from "react-dom/server";
import { afterEach, describe, expect, it } from "vitest";
import { AthleteChooser } from "../components/AthleteChooser";
import { AthleteMarketTags, SeasonAverageBadge } from "./AthleteValueTags";
import { OfferValueSummary, useValuePrefilledBid } from "./useValuePrefilledBid";

function entry(id: string, extra: Partial<LeagueListoneEntry> = {}): LeagueListoneEntry {
  return {
    athleteId: id,
    canonicalName: `Calciatore ${id}`,
    photoUrl: null,
    seasonYear: 2026,
    officialRole: "A",
    effectiveRole: "A",
    providerPositionRaw: "Attacker",
    mappingVersion: "v1",
    clubId: "club",
    clubName: "Lazio",
    override: null,
    ...extra,
  };
}

const CURRENT = { value: 6.45, seasonYear: 2026, seasonLabel: "26/27", isCurrent: true };
const PREVIOUS = { value: 6.12, seasonYear: 2025, seasonLabel: "25/26", isCurrent: false };

function host(html: string): HTMLElement {
  const div = document.createElement("div");
  div.innerHTML = html;
  return div;
}

describe("media e Valore nelle righe (1.3)", () => {
  it("media verde della stagione in corso: solo il numero", () => {
    const view = host(renderToStaticMarkup(createElement(SeasonAverageBadge, { average: CURRENT })));
    const badge = view.querySelector(".fa-season-avg");
    expect(badge?.classList.contains("fa-season-avg--current")).toBe(true);
    expect(badge?.querySelector(".fa-season-avg__value")?.textContent).toBe("6,45");
    expect(badge?.textContent).toBe("Media 6,45");
  });

  it("media rossa della stagione scorsa con «25/26»", () => {
    const view = host(renderToStaticMarkup(createElement(SeasonAverageBadge, { average: PREVIOUS })));
    const badge = view.querySelector(".fa-season-avg");
    expect(badge?.classList.contains("fa-season-avg--previous")).toBe(true);
    expect(badge?.querySelector(".fa-season-avg__value")?.textContent).toBe("6,12 · 25/26");
  });

  it("senza media nulla, o «—» nelle colonne", () => {
    expect(renderToStaticMarkup(createElement(SeasonAverageBadge, { average: null }))).toBe("");
    const dash = host(renderToStaticMarkup(createElement(SeasonAverageBadge, { average: null, emptyDash: true })));
    expect(dash.textContent).toBe("—");
  });

  it("«Valore N» solo se c'è; senza Valore né media nessun elemento", () => {
    const both = host(
      renderToStaticMarkup(createElement(AthleteMarketTags, { marketValue: 58, seasonAverage: CURRENT })),
    );
    expect(both.querySelector(".fa-market-value")?.textContent).toBe("Valore 58");
    const onlyAverage = host(
      renderToStaticMarkup(createElement(AthleteMarketTags, { marketValue: null, seasonAverage: PREVIOUS })),
    );
    expect(onlyAverage.querySelector(".fa-market-value")).toBeNull();
    expect(onlyAverage.textContent).toContain("6,12 · 25/26");
    expect(renderToStaticMarkup(createElement(AthleteMarketTags, {}))).toBe("");
  });

  it("l'elenco dei calciatori (asta, svincolati, chiamata live) mostra Valore e media in ogni riga", () => {
    const view = host(
      renderToStaticMarkup(
        createElement(AthleteChooser, {
          entries: [
            entry("a", { marketValue: 58, seasonAverage: CURRENT }),
            entry("b", { marketValue: 12, seasonAverage: PREVIOUS }),
            entry("c"),
          ],
          ownedAthleteIds: new Set<string>(),
          selected: [],
          onToggle: () => undefined,
          single: true,
          testId: "chooser",
        }),
      ),
    );
    expect(view.querySelector('[data-testid="chooser-a"]')?.textContent).toContain("Valore 58");
    expect(view.querySelector('[data-testid="chooser-a"] .fa-season-avg--current')?.textContent).toContain("6,45");
    expect(view.querySelector('[data-testid="chooser-b"] .fa-season-avg--previous')?.textContent).toContain(
      "6,12 · 25/26",
    );
    expect(view.querySelector('[data-testid="chooser-c"] .fa-market-tags')).toBeNull();
  });
});

describe("modulo d'offerta che parte dal Valore (buste e svincolati)", () => {
  let root: Root | null = null;
  let container: HTMLDivElement | null = null;

  afterEach(() => {
    act(() => root?.unmount());
    container?.remove();
    root = null;
    container = null;
  });

  const ENTRIES = [
    entry("ferraro", { canonicalName: "M. Ferraro", marketValue: 58, seasonAverage: CURRENT }),
    entry("santoro", { canonicalName: "L. Santoro", marketValue: 24, seasonAverage: CURRENT }),
    entry("greco", { canonicalName: "D. Greco" }),
  ];

  function Harness({ balance }: { balance: number | null }) {
    const bid = useValuePrefilledBid(ENTRIES, balance);
    return createElement(
      "div",
      null,
      ...ENTRIES.map((row) =>
        createElement(
          "button",
          { key: row.athleteId, type: "button", "data-pick": row.athleteId, onClick: () => bid.selectAthlete(row.athleteId) },
          row.canonicalName,
        ),
      ),
      createElement("input", {
        "data-testid": "amount",
        value: bid.amount,
        onChange: (event: { target: { value: string } }) => bid.changeAmount(event.target.value),
      }),
      createElement(OfferValueSummary, { selected: bid.selected, prefill: bid.prefill, testId: "offer" }),
    );
  }

  function render(balance: number | null) {
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);
    act(() => root?.render(createElement(Harness, { balance })));
    return container;
  }

  function pick(view: HTMLElement, id: string) {
    act(() => (view.querySelector(`[data-pick="${id}"]`) as HTMLButtonElement).click());
  }

  function amount(view: HTMLElement): string {
    return (view.querySelector('[data-testid="amount"]') as HTMLInputElement).value;
  }

  it("Valore sotto i crediti: l'offerta parte dal Valore", () => {
    const view = render(40);
    expect(amount(view)).toBe("");
    pick(view, "santoro");
    expect(amount(view)).toBe("24");
    expect(view.querySelector('[data-testid="offer-hint"]')?.textContent).toBe(
      "Proposta in base al Valore. Puoi offrire di più o di meno.",
    );
  });

  it("Valore sopra i crediti: parte dai crediti con la riga «hai solo X crediti»", () => {
    const view = render(40);
    pick(view, "ferraro");
    expect(amount(view)).toBe("40");
    expect(view.querySelector('[data-testid="offer"]')?.textContent).toContain("Valore 58");
    expect(view.querySelector('[data-testid="offer-hint"]')?.textContent).toBe(
      "Valore 58: hai solo 40 crediti, l'offerta parte da 40.",
    );
  });

  it("senza Valore il campo resta com'era (vuoto), senza riga", () => {
    const view = render(40);
    pick(view, "greco");
    expect(amount(view)).toBe("");
    expect(view.querySelector('[data-testid="offer-hint"]')).toBeNull();
    // Il numero messo dal Valore di un altro calciatore non resta su quello senza Valore.
    pick(view, "santoro");
    expect(amount(view)).toBe("24");
    pick(view, "greco");
    expect(amount(view)).toBe("");
  });
});
