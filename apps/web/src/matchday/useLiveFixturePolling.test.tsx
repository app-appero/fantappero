import type { FixtureLiveDetail } from "@fantappero/contracts";
import { act, createElement, useState } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const fetchFixtureLiveDetailMock = vi.fn();
vi.mock("../api/leagues", () => ({
  fetchFixtureLiveDetail: (...args: unknown[]) => fetchFixtureLiveDetailMock(...args),
}));

import { clearStoredSession, saveStoredSession } from "../auth/sessionStorage";
import { useLiveFixturePolling } from "./useLiveFixturePolling";

function baseDetail(overrides: Partial<FixtureLiveDetail> = {}): FixtureLiveDetail {
  return {
    fixtureId: "fx-1",
    turnId: "turn-1",
    leagueId: "league-1",
    providerId: 1,
    competitionName: "Serie A",
    homeClubId: "club-home",
    awayClubId: "club-away",
    homeClubName: "Roma FC",
    awayClubName: "Milan FC",
    homeClubLogoUrl: null,
    awayClubLogoUrl: null,
    homeGoals: 1,
    awayGoals: 0,
    statusShort: "2H",
    statusElapsed: 63,
    venueName: null,
    venueCity: null,
    referee: null,
    kickoffAt: "2026-01-01T14:00:00Z",
    updatedAt: "2026-01-01T15:03:00Z",
    feedState: "fresh",
    feedStateLabel: "Aggiornato",
    homeLineup: null,
    awayLineup: null,
    events: [],
    ...overrides,
  };
}

function readHarness(container: HTMLDivElement): { degraded: boolean; statusShort: string } {
  const text = container.querySelector('[data-testid="harness"]')?.textContent ?? "{}";
  return JSON.parse(text) as { degraded: boolean; statusShort: string };
}

function Harness({ initial }: { initial: FixtureLiveDetail }) {
  const [detail, setDetail] = useState(initial);
  const { degraded } = useLiveFixturePolling(
    "league-1",
    "turn-1",
    "fx-1",
    detail,
    setDetail,
    true,
  );
  return createElement(
    "div",
    { "data-testid": "harness" },
    JSON.stringify({ degraded, statusShort: detail.statusShort }),
  );
}

describe("useLiveFixturePolling", () => {
  let container: HTMLDivElement;
  let root: Root;

  beforeEach(() => {
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);
    fetchFixtureLiveDetailMock.mockReset();
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

  it("polls at the base interval while live and stops once the match is finished", async () => {
    const live = baseDetail();
    const finished = baseDetail({ statusShort: "FT", statusElapsed: 90 });
    fetchFixtureLiveDetailMock.mockResolvedValueOnce(live).mockResolvedValueOnce(finished);

    await act(async () => {
      root.render(createElement(Harness, { initial: live }));
    });

    await act(async () => {
      await vi.advanceTimersByTimeAsync(30_000);
    });
    expect(fetchFixtureLiveDetailMock).toHaveBeenCalledTimes(1);
    expect(readHarness(container).statusShort).toBe("2H");

    await act(async () => {
      await vi.advanceTimersByTimeAsync(30_000);
    });
    expect(fetchFixtureLiveDetailMock).toHaveBeenCalledTimes(2);
    expect(readHarness(container).statusShort).toBe("FT");

    // Finished: no further polling even after another interval.
    await act(async () => {
      await vi.advanceTimersByTimeAsync(120_000);
    });
    expect(fetchFixtureLiveDetailMock).toHaveBeenCalledTimes(2);
  });

  it("does not poll a fixture that is not live", async () => {
    const scheduled = baseDetail({ statusShort: "NS", statusElapsed: null });

    await act(async () => {
      root.render(createElement(Harness, { initial: scheduled }));
    });

    await act(async () => {
      await vi.advanceTimersByTimeAsync(120_000);
    });
    expect(fetchFixtureLiveDetailMock).not.toHaveBeenCalled();
  });

  it("backs off and reports degraded on failure, then recovers on success", async () => {
    const live = baseDetail();
    fetchFixtureLiveDetailMock
      .mockRejectedValueOnce(new Error("network down"))
      .mockResolvedValueOnce(live);

    await act(async () => {
      root.render(createElement(Harness, { initial: live }));
    });

    await act(async () => {
      await vi.advanceTimersByTimeAsync(30_000);
    });
    expect(fetchFixtureLiveDetailMock).toHaveBeenCalledTimes(1);
    expect(readHarness(container).degraded).toBe(true);

    // Backed off to double the interval (60s) — not due yet at +30s.
    await act(async () => {
      await vi.advanceTimersByTimeAsync(30_000);
    });
    expect(fetchFixtureLiveDetailMock).toHaveBeenCalledTimes(1);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(30_000);
    });
    expect(fetchFixtureLiveDetailMock).toHaveBeenCalledTimes(2);
    expect(readHarness(container).degraded).toBe(false);
  });
});
