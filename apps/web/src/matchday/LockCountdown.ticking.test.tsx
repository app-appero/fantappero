import { LockCountdown } from "@fantappero/ui";
import { act, createElement } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

describe("LockCountdown ticking (EP-turni-automazione)", () => {
  let container: HTMLDivElement;
  let root: Root;

  beforeEach(() => {
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-01-01T16:00:00.000Z"));
  });

  afterEach(() => {
    act(() => {
      root.unmount();
    });
    vi.useRealTimers();
    container.remove();
  });

  it("ticks the displayed value down every second", async () => {
    await act(async () => {
      root.render(
        createElement(LockCountdown, {
          state: "counting_down",
          nextLockAt: "2026-01-01T16:00:03.000Z",
        }),
      );
    });
    expect(container.textContent).toContain("00:00:03");

    await act(async () => {
      vi.advanceTimersByTime(1_000);
    });
    expect(container.textContent).toContain("00:00:02");
  });

  it("calls onExpire exactly once when the countdown reaches zero", async () => {
    const onExpire = vi.fn();
    await act(async () => {
      root.render(
        createElement(LockCountdown, {
          state: "counting_down",
          nextLockAt: "2026-01-01T16:00:02.000Z",
          onExpire,
        }),
      );
    });
    expect(onExpire).not.toHaveBeenCalled();

    await act(async () => {
      vi.advanceTimersByTime(2_000);
    });
    expect(container.textContent).toContain("00:00:00");
    expect(onExpire).toHaveBeenCalledTimes(1);

    await act(async () => {
      vi.advanceTimersByTime(3_000);
    });
    expect(onExpire).toHaveBeenCalledTimes(1);
  });
});
