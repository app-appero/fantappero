import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { RoleGroupedAthletes } from "./RoleGroupedAthletes";

describe("proposta di scambio con Valore e media (1.3)", () => {
  it("ogni calciatore della proposta ha Valore e media; il prezzo d'acquisto resta a destra", () => {
    const host = document.createElement("div");
    host.innerHTML = renderToStaticMarkup(
      createElement(RoleGroupedAthletes, {
        rows: [
          {
            athleteId: "greco",
            name: "D. Greco",
            role: "D",
            price: 14,
            marketValue: 12,
            seasonAverage: { value: 6.3, seasonYear: 2025, seasonLabel: "25/26", isCurrent: false },
          },
          { athleteId: "barella", name: "N. Barella", role: "C", price: 35 },
        ],
        checked: [],
        onToggle: () => undefined,
      }),
    );
    const labels = Array.from(host.querySelectorAll(".fa-trade-athlete-list label"));
    expect(labels[0]?.querySelector(".fa-market-value")?.textContent).toBe("Valore 12");
    expect(labels[0]?.querySelector(".fa-season-avg--previous")?.textContent).toBe("Media 6,30 · 25/26");
    expect(labels[0]?.querySelector(".fa-trade-role__price")?.textContent).toBe("14");
    // Senza dati 1.3 la riga resta com'era.
    expect(labels[1]?.querySelector(".fa-market-tags")).toBeNull();
    expect(labels[1]?.textContent).toContain("N. Barella");
  });
});
