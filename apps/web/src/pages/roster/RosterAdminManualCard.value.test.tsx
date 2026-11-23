import type { AthleteSeasonAverage, LeagueListoneEntry } from "@fantappero/contracts";
import { act, createElement } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, describe, expect, it, vi } from "vitest";
import { DEMO_TEAM, DEMO_TEAMS } from "./rosterDemoData";
import { RosterAdminManualCard } from "./RosterAdminManualCard";
import type { AthleteOwnership, RoleTab } from "./rosterHelpers";

/** Valore e media nel listone «Inserimento manuale» (1.3, Rosario 21–22/11). */

function average(value: number, isCurrent: boolean): AthleteSeasonAverage {
  return isCurrent
    ? { value, seasonYear: 2026, seasonLabel: "26/27", isCurrent: true }
    : { value, seasonYear: 2025, seasonLabel: "25/26", isCurrent: false };
}

function athlete(id: string, name: string, extra: Partial<LeagueListoneEntry> = {}): LeagueListoneEntry {
  return {
    athleteId: id,
    canonicalName: name,
    photoUrl: null,
    seasonYear: 2026,
    officialRole: "D",
    effectiveRole: "D",
    providerPositionRaw: "Defender",
    mappingVersion: "v1",
    clubId: "lazio",
    clubName: "Lazio",
    competitionId: "c-ita",
    competitionName: "Serie A",
    override: null,
    ...extra,
  };
}

// Nell'ordine del listone (alfabetico): Bianchi senza media, Greco media scorsa, Marchi bassa,
// Santoro e Ferraro della stagione in corso.
const LISTONE: LeagueListoneEntry[] = [
  athlete("bianchi", "A. Bianchi", { marketValue: null, seasonAverage: null }),
  athlete("ferraro", "M. Ferraro", { marketValue: 58, seasonAverage: average(6.85, true) }),
  athlete("greco", "D. Greco", { marketValue: 12, seasonAverage: average(6.3, false) }),
  athlete("marchi", "A. Marchi", { marketValue: 3, seasonAverage: average(5.9, true) }),
  athlete("santoro", "L. Santoro", { marketValue: 24, seasonAverage: average(6.52, true) }),
];

const PLACE_LISTONE: LeagueListoneEntry[] = [
  ...LISTONE,
  athlete("ars", "B. Saka", {
    clubId: "ars",
    clubName: "Arsenal",
    competitionId: "c-eng",
    competitionName: "Premier League",
    marketValue: 40,
    seasonAverage: average(7.1, true),
  }),
];

describe("listone con Valore e media (1.3)", () => {
  let root: Root | null = null;
  let container: HTMLDivElement | null = null;

  afterEach(() => {
    act(() => root?.unmount());
    container?.remove();
    root = null;
    container = null;
  });

  function render(
    options: {
      listone?: LeagueListoneEntry[];
      isAdmin?: boolean;
      remainingCredits?: number | null;
      onAssign?: (athleteId: string, credits: number) => void;
      ownership?: Map<string, AthleteOwnership>;
      onRoleTabChange?: (value: RoleTab) => void;
    } = {},
  ): HTMLDivElement {
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);
    act(() => {
      root?.render(
        createElement(RosterAdminManualCard, {
          isAdmin: options.isAdmin ?? true,
          adminLoadError: null,
          leagueTeams: DEMO_TEAMS,
          targetTeam: DEMO_TEAM,
          emptySlotsCount: 10,
          adminMessage: null,
          adminError: null,
          listone: options.listone ?? LISTONE,
          listoneQuery: "",
          onListoneQueryChange: () => undefined,
          roleTab: "all",
          onRoleTabChange: options.onRoleTabChange ?? (() => undefined),
          ownership: options.ownership ?? new Map(),
          canReleaseAthlete: () => true,
          adminBusy: false,
          remainingCredits: options.remainingCredits === undefined ? 40 : options.remainingCredits,
          onReleaseAthlete: () => undefined,
          onAssignAthlete: options.onAssign ?? (() => undefined),
        }),
      );
    });
    return container;
  }

  const byTestId = (view: HTMLElement, id: string) =>
    view.querySelector<HTMLElement>(`[data-testid="${id}"]`);

  function names(view: HTMLElement): string[] {
    const table = byTestId(view, "roster-admin-listone-table-all");
    return Array.from(table?.querySelectorAll("tbody tr .fa-auction-player__name") ?? []).map(
      (cell) => cell.textContent ?? "",
    );
  }

  function toggle(view: HTMLElement, id: string) {
    const box = byTestId(view, id) as HTMLInputElement;
    act(() => box.click());
  }

  function price(view: HTMLElement, id: string): HTMLInputElement {
    return byTestId(view, `roster-admin-listone-price-${id}`) as HTMLInputElement;
  }

  it("ogni riga ha «Valore N» e la media: verde in corso, rossa con la stagione, niente se manca", () => {
    const view = render();
    const ferraro = byTestId(view, "roster-admin-listone-value-ferraro");
    expect(ferraro?.querySelector(".fa-market-value")?.textContent).toBe("Valore 58");
    expect(ferraro?.querySelector(".fa-season-avg--current .fa-season-avg__value")?.textContent).toBe("6,85");
    const greco = byTestId(view, "roster-admin-listone-value-greco");
    expect(greco?.querySelector(".fa-season-avg--previous .fa-season-avg__value")?.textContent).toBe(
      "6,30 · 25/26",
    );
    const bianchi = byTestId(view, "roster-admin-listone-value-bianchi");
    expect(bianchi?.querySelector(".fa-market-value")).toBeNull();
    expect(bianchi?.querySelector(".fa-season-avg")).toBeNull();
    expect(byTestId(view, "roster-listone-value-hint")?.textContent).toBe(
      "Il prezzo parte dal Valore: puoi cambiarlo prima di assegnare.",
    );
  });

  it("listone senza dati 1.3 (backend più vecchio): nessuna colonna e prezzo da 1 come prima", () => {
    const oldListone = LISTONE.map((entry) => {
      const copy: LeagueListoneEntry = { ...entry };
      delete copy.marketValue;
      delete copy.seasonAverage;
      return copy;
    });
    const view = render({ listone: oldListone });
    expect(view.querySelector(".fa-roster-col--value")).toBeNull();
    expect(byTestId(view, "roster-listone-value-hint")).toBeNull();
    expect(price(view, "ferraro").value).toBe("1");
  });

  it("«Ordina per media» mette la media più alta in cima e chi non ce l'ha in fondo", () => {
    const view = render();
    expect(names(view)).toEqual(["A. Bianchi", "M. Ferraro", "D. Greco", "A. Marchi", "L. Santoro"]);
    const sort = byTestId(view, "roster-listone-sort-average") as HTMLInputElement;
    expect(sort.checked).toBe(false);
    expect(sort.closest(".fa-listone-filters__checks")?.textContent).toContain("Solo disponibili");
    toggle(view, "roster-listone-sort-average");
    expect(names(view)).toEqual(["M. Ferraro", "L. Santoro", "D. Greco", "A. Marchi", "A. Bianchi"]);
    toggle(view, "roster-listone-sort-average");
    expect(names(view)).toEqual(["A. Bianchi", "M. Ferraro", "D. Greco", "A. Marchi", "L. Santoro"]);
  });

  it("«Azzera filtri» toglie «Ordina per media» e lascia «Solo disponibili» com'è", () => {
    const roleChanges: RoleTab[] = [];
    const view = render({ listone: PLACE_LISTONE, onRoleTabChange: (value) => roleChanges.push(value) });
    toggle(view, "roster-listone-only-free");
    toggle(view, "roster-listone-sort-average");
    const competition = byTestId(view, "roster-listone-competition") as HTMLSelectElement;
    act(() => {
      competition.value = "c-ita";
      competition.dispatchEvent(new Event("change", { bubbles: true }));
    });
    act(() => (byTestId(view, "roster-listone-reset-filters") as HTMLButtonElement).click());
    expect((byTestId(view, "roster-listone-sort-average") as HTMLInputElement).checked).toBe(false);
    expect((byTestId(view, "roster-listone-only-free") as HTMLInputElement).checked).toBe(true);
    expect(roleChanges).toEqual(["all"]);
    expect(names(view)[0]).toBe("A. Bianchi");
  });

  it("prezzo dal Valore se ci stai dentro coi crediti, modificabile", () => {
    const onAssign = vi.fn();
    const view = render({ remainingCredits: 40, onAssign });
    const input = price(view, "santoro");
    expect(input.value).toBe("24");
    expect(input.classList.contains("fa-roster-price-input--suggested")).toBe(true);
    expect(byTestId(view, "roster-admin-listone-capped-santoro")).toBeNull();
    act(() => {
      const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")?.set;
      setter?.call(input, "30");
      input.dispatchEvent(new Event("input", { bubbles: true }));
    });
    expect(price(view, "santoro").value).toBe("30");
    expect(price(view, "santoro").classList.contains("fa-roster-price-input--suggested")).toBe(false);
    act(() => (byTestId(view, "roster-admin-assign-santoro") as HTMLButtonElement).click());
    expect(onAssign).toHaveBeenCalledWith("santoro", 30);
  });

  it("Valore oltre i crediti: parte dai crediti rimasti con «Valore N: hai solo X crediti»", () => {
    const onAssign = vi.fn();
    const view = render({ remainingCredits: 40, onAssign });
    expect(price(view, "ferraro").value).toBe("40");
    expect(byTestId(view, "roster-admin-listone-capped-ferraro")?.textContent).toBe(
      "Valore 58: hai solo 40 crediti",
    );
    act(() => (byTestId(view, "roster-admin-assign-ferraro") as HTMLButtonElement).click());
    expect(onAssign).toHaveBeenCalledWith("ferraro", 40);
  });

  it("senza Valore il prezzo resta 1, come oggi", () => {
    const view = render({ remainingCredits: 40 });
    expect(price(view, "bianchi").value).toBe("1");
    expect(price(view, "bianchi").classList.contains("fa-roster-price-input--suggested")).toBe(false);
  });

  it("admin con 0 crediti: parte da 0 e può assegnare a 0", () => {
    const onAssign = vi.fn();
    const view = render({ isAdmin: true, remainingCredits: 0, onAssign });
    expect(price(view, "marchi").value).toBe("0");
    expect(price(view, "marchi").min).toBe("0");
    expect(byTestId(view, "roster-admin-listone-capped-marchi")?.textContent).toBe("Valore 3: hai solo 0 crediti");
    const assign = byTestId(view, "roster-admin-assign-marchi") as HTMLButtonElement;
    expect(assign.disabled).toBe(false);
    act(() => assign.click());
    expect(onAssign).toHaveBeenCalledWith("marchi", 0);
  });

  it("partecipante: il minimo resta 1 credito anche con 0 crediti", () => {
    const view = render({ isAdmin: false, remainingCredits: 0 });
    expect(price(view, "marchi").value).toBe("1");
    expect(price(view, "marchi").min).toBe("1");
    expect(byTestId(view, "roster-admin-listone-capped-marchi")?.textContent).toBe("Valore 3: hai solo 0 crediti");
  });
});
