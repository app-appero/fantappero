import { createElement, useState } from "react";
import { createRoot, type Root } from "react-dom/client";
import { act } from "react";
import { afterEach, describe, expect, it } from "vitest";
import type { FantasyRosterSlot, FantasyTeam, LeagueListoneEntry } from "@fantappero/contracts";
import { DEMO_TEAM, DEMO_TEAMS } from "./rosterDemoData";
import { RosterAdminManualCard } from "./RosterAdminManualCard";
import type { AthleteOwnership, RoleTab } from "./rosterHelpers";

const entries: LeagueListoneEntry[] = Array.from({ length: 25 }, (_, index) => ({
  athleteId: `athlete-${index}`,
  canonicalName: `Calciatore ${index}`,
  photoUrl: null,
  seasonYear: 2026,
  officialRole: "D",
  effectiveRole: "D",
  providerPositionRaw: "Defender",
  mappingVersion: "v1",
  clubId: null,
  clubName: "Club",
  override: null,
}));

function Harness() {
  const [generation, setGeneration] = useState(0);
  const [ownership, setOwnership] = useState<Map<string, AthleteOwnership>>(new Map());
  const listone = entries.map((entry) => ({ ...entry, mappingVersion: `v${generation}` }));
  return createElement(
    "div",
    null,
    createElement(
      "button",
      {
        type: "button",
        onClick: () => {
          setGeneration((current) => current + 1);
          setOwnership(
            new Map([
              [
                "athlete-20",
                { teamId: DEMO_TEAM.id, teamName: DEMO_TEAM.name, slotIndex: 3 },
              ],
            ]),
          );
        },
      },
      "aggiorna",
    ),
    createElement(RosterAdminManualCard, {
      isAdmin: true,
      adminLoadError: null,
      leagueTeams: DEMO_TEAMS,
      targetTeam: DEMO_TEAM,
      emptySlotsCount: 10,
      adminMessage: null,
      adminError: null,
      listone,
      listoneQuery: "",
      onListoneQueryChange: () => undefined,
      roleTab: "all",
      onRoleTabChange: () => undefined,
      ownership,
      canReleaseAthlete: () => true,
      adminBusy: false,
      onReleaseAthlete: () => undefined,
      onAssignAthlete: () => undefined,
    }),
  );
}

describe("listone pagination stays on the clicked page", () => {
  let root: Root | null = null;
  let container: HTMLDivElement | null = null;

  afterEach(() => {
    act(() => {
      root?.unmount();
    });
    container?.remove();
    root = null;
    container = null;
  });

  it("keeps page 2 when the roster update refreshes the same listone", () => {
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);
    act(() => {
      root?.render(createElement(Harness));
    });

    const pagination = container.querySelector(
      '[data-testid="roster-admin-listone-pagination-all"]',
    );
    expect(pagination?.textContent).toContain("Pagina 1 di 2");
    const next = Array.from(pagination?.querySelectorAll("button") ?? []).find((button) =>
      button.textContent?.includes("Successiva"),
    );
    act(() => {
      next?.click();
    });
    expect(pagination?.textContent).toContain("Pagina 2 di 2");

    const refresh = Array.from(container.querySelectorAll("button")).find((button) =>
      button.textContent?.includes("aggiorna"),
    );
    act(() => {
      refresh?.click();
    });

    const samePage = container.querySelector(
      '[data-testid="roster-admin-listone-pagination-all"]',
    );
    expect(samePage?.textContent).toContain("Pagina 2 di 2");
    expect(container.textContent).toContain("Rosa demo");
    expect(container.textContent).toContain("Calciatore 20");
  });

  it("hides owned players until a search asks for them", () => {
    function FilterHarness() {
      const [query, setQuery] = useState("");
      const ownership = new Map<string, AthleteOwnership>([
        ["athlete-0", { teamId: DEMO_TEAM.id, teamName: DEMO_TEAM.name, slotIndex: 0 }],
      ]);
      return createElement(RosterAdminManualCard, {
        isAdmin: true,
        adminLoadError: null,
        leagueTeams: DEMO_TEAMS,
        targetTeam: DEMO_TEAM,
        emptySlotsCount: 10,
        adminMessage: null,
        adminError: null,
        listone: entries.slice(0, 3),
        listoneQuery: query,
        onListoneQueryChange: setQuery,
        roleTab: "all",
        onRoleTabChange: () => undefined,
        ownership,
        canReleaseAthlete: () => true,
        adminBusy: false,
        onReleaseAthlete: () => undefined,
        onAssignAthlete: () => undefined,
      });
    }

    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);
    act(() => {
      root?.render(createElement(FilterHarness));
    });
    expect(container.textContent).toContain("Calciatore 0");
    expect(container.textContent).toContain("Calciatore 1");

    const checkbox = container.querySelector(
      '[data-testid="roster-listone-only-free"]',
    ) as HTMLInputElement;
    act(() => {
      checkbox.click();
    });
    expect(container.textContent).not.toContain("Calciatore 0");
    expect(container.textContent).toContain("Calciatore 1");

    const search = container.querySelector(
      '[data-testid="roster-admin-listone-search"]',
    ) as HTMLInputElement;
    act(() => {
      const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")?.set;
      setter?.call(search, "Calciatore 0");
      search.dispatchEvent(new Event("input", { bubbles: true }));
      search.dispatchEvent(new Event("change", { bubbles: true }));
    });
    expect(container.textContent).toContain("Calciatore 0");
    expect(container.textContent).not.toContain("Calciatore 1");
  });
});

describe("filtri Campionato e Squadra nella ricerca del listone (Rosario, 21/11)", () => {
  const SERIE_A = { competitionId: "c-ita", competitionName: "Serie A" };
  const PREMIER = { competitionId: "c-eng", competitionName: "Premier League" };
  const LALIGA = { competitionId: "c-esp", competitionName: "La Liga" };

  function player(
    id: string,
    clubId: string,
    clubName: string,
    competition: { competitionId: string; competitionName: string } | null,
  ): LeagueListoneEntry {
    return {
      ...entries[0]!,
      athleteId: id,
      canonicalName: `Giocatore ${id}`,
      clubId,
      clubName,
      ...(competition ?? {}),
    };
  }

  const multiListone: LeagueListoneEntry[] = [
    ...Array.from({ length: 22 }, (_, index) => player(`fio-${index}`, "fio", "Fiorentina", SERIE_A)),
    player("ata-0", "ata", "Atalanta", SERIE_A),
    player("ata-1", "ata", "Atalanta", SERIE_A),
    player("ars-0", "ars", "Arsenal", PREMIER),
    player("ars-1", "ars", "Arsenal", PREMIER),
    player("ars-2", "ars", "Arsenal", PREMIER),
    player("atm-0", "atm", "Atlético Madrid", LALIGA),
  ];

  let root: Root | null = null;
  let container: HTMLDivElement | null = null;

  afterEach(() => {
    act(() => {
      root?.unmount();
    });
    container?.remove();
    root = null;
    container = null;
  });

  function render(
    listone: LeagueListoneEntry[],
    roleProps: { roleTab?: RoleTab; onRoleTabChange?: (value: RoleTab) => void } = {},
  ): HTMLDivElement {
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);
    act(() => {
      root?.render(
        createElement(RosterAdminManualCard, {
          isAdmin: true,
          adminLoadError: null,
          leagueTeams: DEMO_TEAMS,
          targetTeam: DEMO_TEAM,
          emptySlotsCount: 10,
          adminMessage: null,
          adminError: null,
          listone,
          listoneQuery: "",
          onListoneQueryChange: () => undefined,
          roleTab: roleProps.roleTab ?? "all",
          onRoleTabChange: roleProps.onRoleTabChange ?? (() => undefined),
          ownership: new Map(),
          canReleaseAthlete: () => true,
          adminBusy: false,
          onReleaseAthlete: () => undefined,
          onAssignAthlete: () => undefined,
        }),
      );
    });
    return container;
  }

  function select(root: HTMLElement, testId: string): HTMLSelectElement | null {
    return root.querySelector(`[data-testid="${testId}"]`);
  }

  function optionLabels(element: HTMLSelectElement | null): string[] {
    return Array.from(element?.options ?? []).map((option) => option.textContent ?? "");
  }

  function choose(root: HTMLElement, testId: string, value: string) {
    const element = select(root, testId);
    expect(element).not.toBeNull();
    act(() => {
      element!.value = value;
      element!.dispatchEvent(new Event("change", { bubbles: true }));
    });
  }

  function click(root: HTMLElement, testId: string) {
    const button = root.querySelector(`[data-testid="${testId}"]`) as HTMLButtonElement | null;
    expect(button).not.toBeNull();
    act(() => {
      button!.click();
    });
  }

  function count(root: HTMLElement): string | null | undefined {
    return root.querySelector('[data-testid="roster-listone-count"]')?.textContent;
  }

  it("mostra Campionato e Squadra sotto la ricerca, con le squadre in ordine e i calciatori", () => {
    const view = render(multiListone);
    const search = view.querySelector('[data-testid="roster-admin-listone-search"]');
    const filters = view.querySelector('[data-testid="roster-listone-filters"]');
    expect(search && filters && search.compareDocumentPosition(filters) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(optionLabels(select(view, "roster-listone-competition"))).toEqual([
      "Tutti i campionati",
      "La Liga",
      "Premier League",
      "Serie A",
    ]);
    expect(optionLabels(select(view, "roster-listone-club"))).toEqual([
      "Tutte le squadre",
      "Arsenal (3)",
      "Atalanta (2)",
      "Atlético Madrid (1)",
      "Fiorentina (22)",
    ]);
    expect(count(view)).toBe("28 calciatori");
    expect(view.querySelector('[data-testid="roster-listone-reset-filters"]')).toBeNull();
  });

  it("scegliendo il campionato la Squadra elenca solo i suoi club e il conto segue i filtri", () => {
    const view = render(multiListone);
    choose(view, "roster-listone-competition", "c-ita");
    expect(optionLabels(select(view, "roster-listone-club"))).toEqual([
      "Tutte le squadre",
      "Atalanta (2)",
      "Fiorentina (22)",
    ]);
    expect(count(view)).toBe("24 calciatori");
    expect(view.querySelector('[data-testid="roster-listone-chip-competition"]')?.textContent).toContain("Serie A");
    expect(view.textContent).toContain("Azzera filtri");

    choose(view, "roster-listone-club", "ata");
    expect(count(view)).toBe("2 calciatori");
    expect(view.textContent).toContain("Giocatore ata-0");
    expect(view.textContent).not.toContain("Giocatore fio-0");
  });

  it("scegliere un campionato azzera una squadra che non ci gioca", () => {
    const view = render(multiListone);
    choose(view, "roster-listone-club", "ars");
    expect(count(view)).toBe("3 calciatori");
    choose(view, "roster-listone-competition", "c-ita");
    expect(select(view, "roster-listone-club")?.value).toBe("");
    expect(view.querySelector('[data-testid="roster-listone-chip-club"]')).toBeNull();
    expect(count(view)).toBe("24 calciatori");
  });

  it("ogni filtro attivo si toglie da solo, «Azzera filtri» li toglie tutti", () => {
    const view = render(multiListone);
    choose(view, "roster-listone-competition", "c-ita");
    choose(view, "roster-listone-club", "fio");
    const clubChip = view.querySelector('[data-testid="roster-listone-chip-club"]');
    expect(clubChip?.getAttribute("aria-label")).toBe("Togli il filtro Squadra: Fiorentina");

    click(view, "roster-listone-chip-club");
    expect(select(view, "roster-listone-club")?.value).toBe("");
    expect(select(view, "roster-listone-competition")?.value).toBe("c-ita");

    choose(view, "roster-listone-club", "fio");
    click(view, "roster-listone-reset-filters");
    expect(select(view, "roster-listone-competition")?.value).toBe("");
    expect(select(view, "roster-listone-club")?.value).toBe("");
    expect(view.querySelector('[data-testid="roster-listone-chip-competition"]')).toBeNull();
    expect(count(view)).toBe("28 calciatori");
  });

  it("«Azzera filtri» riporta anche il ruolo su «Tutti» (Rosario, 21/11)", () => {
    const roleChanges: RoleTab[] = [];
    const view = render(multiListone, {
      roleTab: "P",
      onRoleTabChange: (value) => roleChanges.push(value),
    });
    choose(view, "roster-listone-competition", "c-ita");
    click(view, "roster-listone-reset-filters");
    expect(select(view, "roster-listone-competition")?.value).toBe("");
    expect(roleChanges).toEqual(["all"]);
  });

  it("cambiando un filtro la lista torna a pagina 1", () => {
    const view = render(multiListone);
    const pagination = () => view.querySelector('[data-testid="roster-admin-listone-pagination-all"]');
    const next = Array.from(pagination()?.querySelectorAll("button") ?? []).find((button) =>
      button.textContent?.includes("Successiva"),
    );
    act(() => {
      next?.click();
    });
    expect(pagination()?.textContent).toContain("Pagina 2 di 2");

    choose(view, "roster-listone-club", "fio");
    expect(pagination()?.textContent).toContain("Pagina 1 di 2");
    expect(pagination()?.textContent).toContain("22 calciatori");
  });

  it("con un campionato solo resta solo Squadra", () => {
    const view = render(multiListone.filter((row) => row.competitionId === "c-ita"));
    expect(select(view, "roster-listone-competition")).toBeNull();
    expect(optionLabels(select(view, "roster-listone-club"))).toEqual([
      "Tutte le squadre",
      "Atalanta (2)",
      "Fiorentina (22)",
    ]);
  });

  it("con un backend che non manda il campionato resta solo Squadra, con tutti i club", () => {
    const old = multiListone.map(({ competitionId: _id, competitionName: _name, ...rest }) => rest);
    const view = render(old);
    expect(select(view, "roster-listone-competition")).toBeNull();
    expect(optionLabels(select(view, "roster-listone-club"))).toHaveLength(5);
  });
});

describe("quota per ruolo nel listone (tester, Rosario 21/11)", () => {
  let root: Root | null = null;
  let container: HTMLDivElement | null = null;

  afterEach(() => {
    act(() => {
      root?.unmount();
    });
    container?.remove();
    root = null;
    container = null;
  });

  function slot(index: number, athleteId: string | null, role: string | null): FantasyRosterSlot {
    return {
      id: `slot-${index}`,
      slotIndex: index,
      athleteId,
      athleteName: athleteId,
      photoUrl: null,
      clubName: "Club",
      role,
      purchaseCredits: athleteId ? 1 : null,
      exceedsRoleQuota: false,
    };
  }

  // Dieci attaccanti su dieci e un difensore: gli attaccanti sono al completo, i difensori no.
  const fullForwards: FantasyTeam = {
    ...DEMO_TEAM,
    slots: [
      ...Array.from({ length: 10 }, (_, index) => slot(index, `owned-a-${index}`, "A")),
      slot(10, "owned-d-0", "D"),
      ...Array.from({ length: 5 }, (_, index) => slot(11 + index, null, null)),
    ],
  };
  const quotaListone: LeagueListoneEntry[] = [
    { ...entries[0]!, athleteId: "free-a", canonicalName: "Punta libera", officialRole: "A", effectiveRole: "A" },
    { ...entries[0]!, athleteId: "free-d", canonicalName: "Difensore libero", officialRole: "D", effectiveRole: "D" },
  ];

  function renderCard(roleTab: RoleTab, ownTeamId: string | null, emptySlotsCount = 5) {
    const host = document.createElement("div");
    container = host;
    document.body.appendChild(host);
    root = createRoot(host);
    act(() => {
      root?.render(
        createElement(RosterAdminManualCard, {
          isAdmin: true,
          adminLoadError: null,
          leagueTeams: DEMO_TEAMS,
          targetTeam: fullForwards,
          ownTeamId,
          emptySlotsCount,
          adminMessage: null,
          adminError: null,
          listone: quotaListone,
          listoneQuery: "",
          onListoneQueryChange: () => undefined,
          roleTab,
          onRoleTabChange: () => undefined,
          ownership: new Map(),
          canReleaseAthlete: () => true,
          adminBusy: false,
          onReleaseAthlete: () => undefined,
          onAssignAthlete: () => undefined,
        }),
      );
    });
    return host;
  }

  const assignButton = (host: HTMLElement, athleteId: string) =>
    host.querySelector(`[data-testid="roster-admin-assign-${athleteId}"]`) as HTMLButtonElement | null;
  const notice = (host: HTMLElement, tab: string) =>
    host.querySelector(`[data-testid="roster-admin-quota-notice-${tab}"]`);

  it("scheda Attaccanti: avviso in cima e «+» spento con il motivo", () => {
    const host = renderCard("A", DEMO_TEAM.id);
    expect(notice(host, "A")?.textContent).toBe(
      "Attaccanti al completo: 10 su 10. Per prenderne un altro prima svincolane uno.",
    );
    const button = assignButton(host, "free-a");
    expect(button?.disabled).toBe(true);
    expect(button?.getAttribute("aria-label")).toBe(
      "Non puoi assegnare Punta libera. Attaccanti al completo: 10 su 10. Per prenderne un altro prima svincolane uno.",
    );
    expect(button?.getAttribute("title")).toContain("Attaccanti al completo");
    expect(host.querySelector('[data-testid="roster-admin-quota-count-A"]')?.textContent?.trim()).toBe("10/10");
  });

  it("scheda Tutti: riga dei ruoli al completo, gli altri ruoli restano assegnabili", () => {
    const host = renderCard("all", DEMO_TEAM.id);
    expect(notice(host, "all")?.textContent).toBe("Al completo: Attaccanti (10/10)");
    expect(assignButton(host, "free-a")?.disabled).toBe(true);
    const defender = assignButton(host, "free-d");
    expect(defender?.disabled).toBe(false);
    expect(defender?.getAttribute("aria-label")).toBe("Assegna Difensore libero");
  });

  it("admin che assegna a un'altra squadra: il messaggio la nomina", () => {
    const host = renderCard("A", "another-team");
    expect(notice(host, "A")?.textContent).toBe(`${DEMO_TEAM.name} ha già 10 attaccanti su 10.`);
  });

  it("rosa piena: nessun avviso di ruolo, assegnazione spenta come prima", () => {
    const host = renderCard("all", DEMO_TEAM.id, 0);
    expect(notice(host, "all")).toBeNull();
    expect(assignButton(host, "free-d")?.disabled).toBe(true);
    expect(assignButton(host, "free-d")?.getAttribute("aria-label")).toBe("Assegna Difensore libero");
  });
});
