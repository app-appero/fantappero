import type { FantasyTurnDetail } from "@fantappero/contracts";
import { act, createElement, useState } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const fetchFantasyTurnMock = vi.fn();
vi.mock("../api/leagues", () => ({
  fetchFantasyTurn: (...args: unknown[]) => fetchFantasyTurnMock(...args),
}));

import { clearStoredSession, saveStoredSession } from "../auth/sessionStorage";
import { useLiveTurnPolling } from "./useLiveTurnPolling";

function baseTurn(overrides: Partial<FantasyTurnDetail> = {}): FantasyTurnDetail {
  return {
    id: "turn-1",
    leagueId: "league-1",
    number: 1,
    kind: "weekend",
    windowStartAt: "2026-01-01T00:00:00Z",
    windowEndAt: "2026-01-05T00:00:00Z",
    opensAt: null,
    closesAt: null,
    cutoffAt: null,
    status: "open",
    effectiveStatus: "open",
    skipReason: null,
    fixtureCount: 0,
    generatedAt: "2026-01-01T00:00:00Z",
    modificationAllowed: false,
    matchStatus: "scheduled",
    homologationStatus: "provisional",
    fixtures: [],
    ...overrides,
  };
}

function readHarness(container: HTMLDivElement): { degraded: boolean; homologationStatus: string } {
  const text = container.querySelector('[data-testid="harness"]')?.textContent ?? "{}";
  return JSON.parse(text) as { degraded: boolean; homologationStatus: string };
}

function Harness({ initial }: { initial: FantasyTurnDetail }) {
  const [turn, setTurn] = useState(initial);
  const { degraded } = useLiveTurnPolling("league-1", turn, setTurn, true);
  return createElement(
    "div",
    { "data-testid": "harness" },
    JSON.stringify({ degraded, homologationStatus: turn.homologationStatus }),
  );
}

describe("useLiveTurnPolling (EP09-04)", () => {
  let container: HTMLDivElement;
  let root: Root;

  beforeEach(() => {
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);
    fetchFantasyTurnMock.mockReset();
    saveStoredSession({
      accessToken: "token-123",
      refreshToken: "refresh-123",
      user: { id: "user-1", displayName: "Membro Test", globalRole: "member" },
    });
    vi.useFakeTimers();
  });

  afterEach(() => {
    act(() => {
      root.unmount();
    });
    vi.useRealTimers();
    container.remove();
    clearStoredSession();
  });

  it("polls at the base interval and stops once the round is homologated", async () => {
    const live = baseTurn();
    const homologated = baseTurn({ homologationStatus: "homologated" });
    fetchFantasyTurnMock.mockResolvedValueOnce(live).mockResolvedValueOnce(homologated);

    await act(async () => {
      root.render(createElement(Harness, { initial: live }));
    });

    await act(async () => {
      await vi.advanceTimersByTimeAsync(15_000);
    });
    expect(fetchFantasyTurnMock).toHaveBeenCalledTimes(1);
    expect(readHarness(container).homologationStatus).toBe("provisional");

    await act(async () => {
      await vi.advanceTimersByTimeAsync(15_000);
    });
    expect(fetchFantasyTurnMock).toHaveBeenCalledTimes(2);
    expect(readHarness(container).homologationStatus).toBe("homologated");

    // Homologated: no further polling even after another interval.
    await act(async () => {
      await vi.advanceTimersByTimeAsync(60_000);
    });
    expect(fetchFantasyTurnMock).toHaveBeenCalledTimes(2);
  });

  it("backs off and reports degraded on failure, then recovers on success", async () => {
    const live = baseTurn();
    fetchFantasyTurnMock
      .mockRejectedValueOnce(new Error("network down"))
      .mockResolvedValueOnce(live);

    await act(async () => {
      root.render(createElement(Harness, { initial: live }));
    });

    await act(async () => {
      await vi.advanceTimersByTimeAsync(15_000);
    });
    expect(fetchFantasyTurnMock).toHaveBeenCalledTimes(1);
    expect(readHarness(container).degraded).toBe(true);

    // Backed off to double the interval (30s) — not due yet at +15s.
    await act(async () => {
      await vi.advanceTimersByTimeAsync(15_000);
    });
    expect(fetchFantasyTurnMock).toHaveBeenCalledTimes(1);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(15_000);
    });
    expect(fetchFantasyTurnMock).toHaveBeenCalledTimes(2);
    expect(readHarness(container).degraded).toBe(false);
  });
});
