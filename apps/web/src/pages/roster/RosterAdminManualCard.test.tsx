import { createElement, useState } from "react";
import { createRoot, type Root } from "react-dom/client";
import { act } from "react";
import { afterEach, describe, expect, it } from "vitest";
import type { LeagueListoneEntry } from "@fantappero/contracts";
import { DEMO_TEAM, DEMO_TEAMS } from "./rosterDemoData";
import { RosterAdminManualCard } from "./RosterAdminManualCard";
import type { AthleteOwnership } from "./rosterHelpers";

const entries: LeagueListoneEntry[] = Array.from({ length: 25 }, (_, index) => ({
  athleteId: `athlete-${index}`,
  canonicalName: `Calciatore ${index}`,
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
