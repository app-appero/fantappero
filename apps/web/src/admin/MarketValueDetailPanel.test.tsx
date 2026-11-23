import { act, createElement } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { VALUE_DETAIL_DONNARUMMA, VALUE_DETAIL_ENTRIES } from "./marketValueDetailFixture";

/**
 * «Dettaglio del Valore» nel Listone del pannello operatore (1.4): ricerca nel listone già
 * caricato, richiesta del dettaglio e lettura in italiano. Il fetch è finto: nessuna chiamata
 * vera.
 */

vi.mock("../auth/sessionStorage", () => ({
  loadStoredSession: () => ({ accessToken: "token-op" }),
}));
vi.mock("../auth/AuthContext", () => ({
  getApiErrorMessage: (_error: unknown, fallback: string) => fallback,
}));

import { MarketValueDetailPanel } from "./MarketValueDetailPanel";

const nativeInputValueSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value")!.set!;

describe("Dettaglio del Valore (pannello operatore)", () => {
  let container: HTMLDivElement;
  let root: Root;
  let urls: string[];
  let status: number;
  let body: unknown;

  beforeEach(() => {
    urls = [];
    status = 200;
    body = VALUE_DETAIL_DONNARUMMA;
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const url = typeof input === "string" ? input : input instanceof URL ? input.href : input.url;
        urls.push(url.replace("http://localhost:59999", ""));
        return new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } });
      }),
    );
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);
  });

  afterEach(() => {
    act(() => root.unmount());
    container.remove();
    vi.unstubAllGlobals();
  });

  const byTestId = (id: string) => container.querySelector<HTMLElement>(`[data-testid="${id}"]`);

  async function flush() {
    for (let index = 0; index < 5; index += 1) {
      await act(async () => {
        await Promise.resolve();
      });
    }
  }

  async function mount(entries = VALUE_DETAIL_ENTRIES) {
    await act(async () => {
      root.render(createElement(MarketValueDetailPanel, { entries, seasonYear: 2026 }));
    });
  }

  async function type(name: string, value: string) {
    const input = container.querySelector<HTMLInputElement>(`input[name="${name}"]`)!;
    await act(async () => {
      nativeInputValueSetter.call(input, value);
      input.dispatchEvent(new Event("input", { bubbles: true }));
    });
  }

  async function click(id: string) {
    await act(async () => {
      byTestId(id)?.dispatchEvent(new MouseEvent("click", { bubbles: true, cancelable: true }));
    });
    await flush();
  }

  it("cerca nel listone (senza accenti) e mostra al massimo i risultati che servono", async () => {
    await mount();
    expect(byTestId("admin-value-detail-results")).toBeNull();
    await type("admin-value-detail-query", "d");
    expect(byTestId("admin-value-detail-results")).toBeNull(); // almeno 2 lettere
    await type("admin-value-detail-query", "martinez");
    expect(byTestId("admin-value-detail-results")?.textContent).toContain("L. Martínez");
    await type("admin-value-detail-query", "manchester");
    expect(byTestId("admin-value-detail-results")?.textContent).toContain("G. Donnarumma");
    expect(byTestId("admin-value-detail-results")?.textContent).not.toContain("Martínez");
    await type("admin-value-detail-query", "zzz");
    expect(byTestId("admin-value-detail-no-results")).not.toBeNull();
    expect(urls).toEqual([]);
  });

  it("scelto il calciatore, mostra la tabella per stagione e il calcolo in italiano", async () => {
    await mount();
    await type("admin-value-detail-query", "donnarumma");
    await click("admin-value-detail-pick-gk-1");

    expect(urls).toEqual(["/admin/listone/valori/gk-1?seasonYear=2026"]);
    expect(byTestId("admin-value-detail-summary")?.textContent).toContain("Valore 8 crediti a budget 1000");
    const table = byTestId("admin-value-detail-table")!;
    const headers = Array.from(table.querySelectorAll("thead th")).map((cell) => cell.textContent);
    expect(headers.slice(1)).toEqual(["2026/27 in corso", "2025/26", "2024/25"]);
    const rows = Array.from(table.querySelectorAll("tbody tr")).map((row) =>
      Array.from(row.children).map((cell) => cell.textContent),
    );
    expect(rows).toContainEqual(["Fonte", "FantApperò", "fornitore", "fornitore"]);
    expect(rows).toContainEqual(["Media", "6,68", "7,03", "6,86"]);
    expect(rows).toContainEqual(["Percentile", "50° · 52° di 118", "76° · 47° di 192", "30° · 131° di 188"]);
    expect(rows).toContainEqual(["Peso", "40%", "36%", "24%"]);

    const steps = Array.from(byTestId("admin-value-detail-steps")!.querySelectorAll("li")).map(
      (item) => item.textContent,
    );
    expect(steps[1]).toContain(
      "Stagione 2025/26 (fornitore, Premier League): 34 presenze, media 7,03 → media ristretta 7,00 (media dei portieri 6,86) → 76° percentile fra 192 portieri, 47° posto → peso 36%",
    );
    expect(steps[1]).toContain("Non contano: UEFA Champions League (coppa, 10 presenze, media 7,40)");
    expect(steps[3]).toBe("Indice combinato p = 40% × 0,50 + 36% × 0,76 + 24% × 0,30 = 0,55");
    expect(steps[4]).toBe("Curva dei portieri: 1 + (30 − 1) × 0,55^2,4 = 7,8 crediti a budget 1000 → 8 crediti");
    expect(byTestId("admin-value-detail-budget-step")).toBeNull();
    expect(container.textContent).toContain("Valore base dei portieri (nessuno storico, p = 0,33): 3 crediti");
  });

  it("con un altro budget aggiunge i crediti della lega", async () => {
    await mount();
    await type("admin-value-detail-query", "donnarumma");
    await click("admin-value-detail-pick-gk-1");
    await type("admin-value-detail-budget", "500");

    expect(byTestId("admin-value-detail-summary")?.textContent).toContain("4 a budget 500");
    expect(byTestId("admin-value-detail-budget-step")?.textContent).toBe(
      "Lega da 500 crediti: 7,8 × 500 / 1000 = 3,90 → 4 crediti",
    );
  });

  it("avvisa se il dettaglio è di una versione vecchia o se il calciatore non è nel listone", async () => {
    body = { ...VALUE_DETAIL_DONNARUMMA, status: "outdated", version: null };
    await mount();
    await type("admin-value-detail-query", "donnarumma");
    await click("admin-value-detail-pick-gk-1");
    expect(byTestId("admin-value-detail-status")?.textContent).toContain("Ricalcola valori");

    status = 404;
    body = { code: "market_value_athlete_not_found", message: "Calciatore non trovato" };
    await click("admin-value-detail-pick-gk-2");
    expect(byTestId("admin-value-detail-error")?.textContent).toContain("non è nel listone");
    expect(byTestId("admin-value-detail-result")).toBeNull();
  });
});
