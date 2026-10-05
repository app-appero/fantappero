import { act, createElement } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const fetchPendingInviteCountMock = vi.fn();

vi.mock("../api/managerInvites", () => ({
  fetchPendingInviteCount: (...args: unknown[]) => fetchPendingInviteCountMock(...args),
}));

import { clearStoredSession, saveStoredSession } from "../auth/sessionStorage";
import { notifyPendingInvitesChanged, usePendingInviteCount } from "./usePendingInviteCount";

function readCount(container: HTMLDivElement): string {
  return container.querySelector('[data-testid="pending-count"]')?.textContent ?? "";
}

function Harness({ enabled }: { enabled: boolean }) {
  const count = usePendingInviteCount(enabled);
  return createElement("span", { "data-testid": "pending-count" }, String(count));
}

describe("usePendingInviteCount (EP13-P07)", () => {
  let container: HTMLDivElement;
  let root: Root;

  beforeEach(() => {
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);
    fetchPendingInviteCountMock.mockReset();
    saveStoredSession({
      accessToken: "token-123",
      refreshToken: "refresh-123",
      user: { id: "user-1", displayName: "Membro Test", globalRole: "member" },
    });
  });

  afterEach(() => {
    act(() => {
      root.unmount();
    });
    container.remove();
    clearStoredSession();
  });

  it("loads the count on mount and again when the window regains focus", async () => {
    fetchPendingInviteCountMock.mockResolvedValue({ pendingInviteCount: 2 });

    await act(async () => {
      root.render(createElement(Harness, { enabled: true }));
    });

    expect(fetchPendingInviteCountMock).toHaveBeenCalledTimes(1);
    expect(fetchPendingInviteCountMock).toHaveBeenCalledWith("token-123");
    expect(readCount(container)).toBe("2");

    fetchPendingInviteCountMock.mockResolvedValue({ pendingInviteCount: 1 });
    await act(async () => {
      window.dispatchEvent(new Event("focus"));
    });

    expect(fetchPendingInviteCountMock).toHaveBeenCalledTimes(2);
    expect(readCount(container)).toBe("1");
  });

  it("drops the badge as soon as an invite is accepted or declined", async () => {
    fetchPendingInviteCountMock.mockResolvedValue({ pendingInviteCount: 1 });

    await act(async () => {
      root.render(createElement(Harness, { enabled: true }));
    });
    expect(readCount(container)).toBe("1");

    fetchPendingInviteCountMock.mockResolvedValue({ pendingInviteCount: 0 });
    await act(async () => {
      notifyPendingInvitesChanged();
    });

    expect(fetchPendingInviteCountMock).toHaveBeenCalledTimes(2);
    expect(readCount(container)).toBe("0");
  });

  it("ignores a slower response that arrives after a newer refresh", async () => {
    let resolveFirst: (value: { pendingInviteCount: number }) => void = () => {};
    const first = new Promise<{ pendingInviteCount: number }>((resolve) => {
      resolveFirst = resolve;
    });
    fetchPendingInviteCountMock.mockImplementationOnce(() => first);
    fetchPendingInviteCountMock.mockResolvedValueOnce({ pendingInviteCount: 0 });

    await act(async () => {
      root.render(createElement(Harness, { enabled: true }));
    });
    expect(readCount(container)).toBe("0");

    await act(async () => {
      notifyPendingInvitesChanged();
    });
    expect(readCount(container)).toBe("0");

    await act(async () => {
      resolveFirst({ pendingInviteCount: 4 });
      await first;
    });

    expect(readCount(container)).toBe("0");
  });

  it("stays at zero when the session cannot see invites", async () => {
    await act(async () => {
      root.render(createElement(Harness, { enabled: false }));
    });

    expect(fetchPendingInviteCountMock).not.toHaveBeenCalled();
    expect(readCount(container)).toBe("0");
  });
});
