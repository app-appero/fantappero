import { act, createElement } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const fetchMock = vi.fn();
const decideMock = vi.fn();

vi.mock("../api/admin", () => ({
  fetchTesterRequests: (...args: unknown[]) => fetchMock(...args),
  decideTesterRequests: (...args: unknown[]) => decideMock(...args),
}));
vi.mock("../auth/AuthContext", () => ({
  getApiErrorMessage: (error: unknown, fallback: string) =>
    error instanceof Error ? error.message : fallback,
}));
vi.mock("../auth/sessionStorage", () => ({
  loadStoredSession: () => ({ accessToken: "t", refreshToken: "r", user: { id: "u" } }),
}));

import { AdminTesterRequestsPanel } from "./AdminTesterRequestsPanel";

const row = {
  id: "r1",
  email: "mario@example.com",
  firstName: "Mario",
  lastName: "Rossi",
  phone: "+39 333 1234567",
  motivation: "Mi piace il fantacalcio",
  status: "pending" as const,
  createdAt: "2026-11-13T10:00:00Z",
};

describe("AdminTesterRequestsPanel", () => {
  let container: HTMLDivElement;
  let root: Root;

  beforeEach(() => {
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);
    fetchMock.mockReset();
    decideMock.mockReset();
  });

  afterEach(() => {
    act(() => root.unmount());
    container.remove();
  });

  it("mostra i dati della richiesta e approva con un tocco", async () => {
    fetchMock.mockResolvedValue({ requests: [row] });
    decideMock.mockResolvedValue({ requests: [{ ...row, status: "approved" }] });
    const onCount = vi.fn();
    await act(async () => {
      root.render(createElement(AdminTesterRequestsPanel, { onPendingCount: onCount }));
    });
    const text = container.textContent ?? "";
    expect(text).toContain("Mario Rossi");
    expect(text).toContain("+39 333 1234567");
    expect(text).toContain("Mi piace il fantacalcio");
    expect(onCount).toHaveBeenLastCalledWith(1);

    await act(async () => {
      container
        .querySelector<HTMLButtonElement>('[data-testid="admin-request-approve-r1"]')
        ?.click();
    });
    expect(decideMock).toHaveBeenCalledWith("t", { ids: ["r1"], action: "approve" });
    expect(onCount).toHaveBeenLastCalledWith(0);
  });
});
