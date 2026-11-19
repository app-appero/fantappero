import type { LeagueListoneEntry } from "@fantappero/contracts";
import { act, createElement } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const fetchAthleteCardMock = vi.fn();

vi.mock("../api/leagues", () => ({
  fetchAthleteCard: (...args: unknown[]) => fetchAthleteCardMock(...args),
}));
vi.mock("../auth/AuthContext", () => ({
  useAuth: () => ({ isDemoMode: false, activeLeagueId: "league-1" }),
}));

import { AthleteCardProvider } from "../athletes/AthleteCard";
import { AthleteChooser } from "./AthleteChooser";

const ENTRY: LeagueListoneEntry = {
  athleteId: "ath-1",
  canonicalName: "Lautaro Martínez",
  photoUrl: null,
  seasonYear: 2026,
  officialRole: "A",
  effectiveRole: "A",
  providerPositionRaw: null,
  mappingVersion: "v1",
  clubId: "club-1",
  clubName: "Inter",
  override: null,
};

describe("AthleteChooser — scelta del calciatore (asta live)", () => {
  let container: HTMLDivElement;
  let root: Root;
  const onToggle = vi.fn();

  const row = () => container.querySelector<HTMLButtonElement>('[data-testid="chooser-ath-1"]');

  async function render() {
    await act(async () => {
      // Con il provider della scheda calciatore attivo, come nella pagina dell'asta.
      root.render(
        createElement(AthleteCardProvider, {
          children: createElement(AthleteChooser, {
            entries: [ENTRY],
            ownedAthleteIds: new Set<string>(),
            selected: [],
            onToggle,
            single: true,
            testId: "chooser",
          }),
        }),
      );
    });
  }

  beforeEach(() => {
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);
    onToggle.mockReset();
    fetchAthleteCardMock.mockReset();
  });

  afterEach(() => {
    act(() => root.unmount());
    container.remove();
  });

  it("il nome nella riga è testo, non un secondo pulsante dentro il pulsante", async () => {
    await render();
    expect(row()).not.toBeNull();
    expect(row()?.querySelector("button")).toBeNull();
    expect(row()?.textContent).toContain("Lautaro Martínez");
  });

  it("toccare il nome seleziona il calciatore e non apre la scheda", async () => {
    await render();
    const name = row()?.querySelector(".fa-athlete-chooser__name")?.firstElementChild;
    expect(name?.textContent).toBe("Lautaro Martínez");
    await act(async () => {
      name?.dispatchEvent(new MouseEvent("click", { bubbles: true, cancelable: true }));
    });
    expect(onToggle).toHaveBeenCalledWith("ath-1");
    expect(fetchAthleteCardMock).not.toHaveBeenCalled();
    expect(document.querySelector('[role="dialog"]')).toBeNull();
  });
});
