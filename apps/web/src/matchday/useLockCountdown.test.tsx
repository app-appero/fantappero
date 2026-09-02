import type { LineupLockCountdown } from "@fantappero/contracts";
import { act, createElement } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const fetchLineupLockCountdownMock = vi.fn();
vi.mock("../api/leagues", () => ({
  fetchLineupLockCountdown: (...args: unknown[]) => fetchLineupLockCountdownMock(...args),
}));

import { clearStoredSession, saveStoredSession } from "../auth/sessionStorage";
import { useLockCountdown } from "./useLockCountdown";

function countdown(overrides: Partial<LineupLockCountdown> = {}): LineupLockCountdown {
  return {
    leagueId: "league-1",
    roundId: "turn-1",
    roundNumber: 3,
    roundStatus: "open",
    state: "counting_down",
    nextLockAt: "2026-01-01T18:00:00Z",
    serverNow: "2026-01-01T16:00:00Z",
    ...overrides,
  };
}

function readHarness(container: HTMLDivElement): { state: string | null } {
  const text = container.querySelector('[data-testid="harness"]')?.textContent ?? "{}";
  return JSON.parse(text) as { state: string | null };
}

let refetchRef: (() => void) | null = null;

function Harness({ leagueId }: { leagueId: string | null }) {
  const { countdown: value, refetch } = useLockCountdown(leagueId);
  refetchRef = refetch;
  return createElement(
    "div",
    { "data-testid": "harness" },
    JSON.stringify({ state: value?.state ?? null }),
  );
}

describe("useLockCountdown (EP-turni-automazione)", () => {
  let container: HTMLDivElement;
  let root: Root;

  beforeEach(() => {
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);
    fetchLineupLockCountdownMock.mockReset();
    refetchRef = null;
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

  it("fetches once on mount and exposes nothing without a league", async () => {
    await act(async () => {
      root.render(createElement(Harness, { leagueId: null }));
    });
    expect(fetchLineupLockCountdownMock).not.toHaveBeenCalled();
    expect(readHarness(container).state).toBeNull();
  });

  it("fetches on mount and refetches on window focus", async () => {
    fetchLineupLockCountdownMock.mockResolvedValue(countdown({ state: "no_pending_lock" }));

    await act(async () => {
      root.render(createElement(Harness, { leagueId: "league-1" }));
    });
    expect(fetchLineupLockCountdownMock).toHaveBeenCalledTimes(1);
    expect(readHarness(container).state).toBe("no_pending_lock");

    await act(async () => {
      window.dispatchEvent(new Event("focus"));
    });
    expect(fetchLineupLockCountdownMock).toHaveBeenCalledTimes(2);
  });

  it("polls every 90s only while counting down, and stops otherwise", async () => {
    fetchLineupLockCountdownMock.mockResolvedValue(countdown({ state: "no_pending_lock" }));

    await act(async () => {
      root.render(createElement(Harness, { leagueId: "league-1" }));
    });
    expect(fetchLineupLockCountdownMock).toHaveBeenCalledTimes(1);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(90_000);
    });
    // Not counting down: no scheduled poll.
    expect(fetchLineupLockCountdownMock).toHaveBeenCalledTimes(1);
  });

  it("keeps polling every 90s while a lock is ticking down", async () => {
    fetchLineupLockCountdownMock.mockResolvedValue(countdown({ state: "counting_down" }));

    await act(async () => {
      root.render(createElement(Harness, { leagueId: "league-1" }));
    });
    expect(fetchLineupLockCountdownMock).toHaveBeenCalledTimes(1);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(90_000);
    });
    expect(fetchLineupLockCountdownMock).toHaveBeenCalledTimes(2);
  });

  it("refetches immediately on demand, e.g. when the ticking countdown reaches zero", async () => {
    fetchLineupLockCountdownMock.mockResolvedValue(countdown({ state: "counting_down" }));

    await act(async () => {
      root.render(createElement(Harness, { leagueId: "league-1" }));
    });
    expect(fetchLineupLockCountdownMock).toHaveBeenCalledTimes(1);

    await act(async () => {
      refetchRef?.();
    });
    expect(fetchLineupLockCountdownMock).toHaveBeenCalledTimes(2);
  });
});
