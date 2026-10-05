import type { NamedLeagueInvite } from "@fantappero/contracts";
import { act, createElement } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const fetchMeMock = vi.fn();
const fetchMyLeaguesMock = vi.fn();
const fetchPendingInviteCountMock = vi.fn();
const fetchReceivedNamedInvitesMock = vi.fn();
const acceptReceivedNamedInviteMock = vi.fn();
const declineReceivedNamedInviteMock = vi.fn();

vi.mock("../api/auth", () => ({
  fetchMe: (...args: unknown[]) => fetchMeMock(...args),
  refresh: vi.fn(),
  login: vi.fn(),
  loginWithGoogle: vi.fn(),
  register: vi.fn(),
  logout: vi.fn(),
  forgotPassword: vi.fn(),
  resetPassword: vi.fn(),
  verifyEmail: vi.fn(),
  resendVerification: vi.fn(),
}));

vi.mock("../api/leagues", () => ({
  fetchMyLeagues: (...args: unknown[]) => fetchMyLeaguesMock(...args),
}));

vi.mock("../api/managerInvites", () => ({
  fetchPendingInviteCount: (...args: unknown[]) => fetchPendingInviteCountMock(...args),
  fetchReceivedNamedInvites: (...args: unknown[]) => fetchReceivedNamedInvitesMock(...args),
  acceptReceivedNamedInvite: (...args: unknown[]) => acceptReceivedNamedInviteMock(...args),
  declineReceivedNamedInvite: (...args: unknown[]) => declineReceivedNamedInviteMock(...args),
}));

import { AuthProvider } from "../auth/AuthContext";
import { clearStoredSession, saveStoredSession } from "../auth/sessionStorage";
import { usePendingInviteCount } from "../layout/usePendingInviteCount";
import { MemoryRouter } from "../router/simpleRouter";
import { ReceivedInvitesPage } from "./ReceivedInvitesPage";

const INVITE: NamedLeagueInvite = {
  id: "invite-1",
  leagueId: "league-1",
  leagueName: "Amici del Bar",
  recipientUserId: "user-1",
  recipientDisplayName: "Membro Test",
  recipientUserType: "human",
  status: "pending",
  createdAt: "2026-08-03T10:00:00Z",
  expiresAt: "2026-08-12T10:00:00Z",
  respondedAt: null,
  autoAccepted: false,
};

function Harness() {
  const count = usePendingInviteCount(true);
  return createElement(
    "div",
    null,
    createElement("span", { "data-testid": "pending-invite-badge" }, String(count)),
    createElement(ReceivedInvitesPage),
  );
}

function badgeText(container: HTMLDivElement): string {
  return container.querySelector('[data-testid="pending-invite-badge"]')?.textContent ?? "";
}

function buttonByLabel(container: HTMLDivElement, label: string): HTMLButtonElement {
  const button = [...container.querySelectorAll("button")].find(
    (candidate) => candidate.textContent === label,
  );
  if (!(button instanceof HTMLButtonElement)) {
    throw new Error(`Pulsante ${label} non trovato`);
  }
  return button;
}

describe("ReceivedInvitesPage aggiorna il badge rosso", () => {
  let container: HTMLDivElement;
  let root: Root;

  beforeEach(() => {
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);
    fetchMeMock.mockReset();
    fetchMyLeaguesMock.mockReset();
    fetchPendingInviteCountMock.mockReset();
    fetchReceivedNamedInvitesMock.mockReset();
    acceptReceivedNamedInviteMock.mockReset();
    declineReceivedNamedInviteMock.mockReset();

    saveStoredSession({
      accessToken: "token-123",
      refreshToken: "refresh-123",
      user: { id: "user-1", displayName: "Membro Test", globalRole: "member" },
    });
    fetchMeMock.mockResolvedValue({
      id: "user-1",
      displayName: "Membro Test",
      globalRole: "member",
    });
    fetchMyLeaguesMock.mockResolvedValue([]);
    fetchPendingInviteCountMock.mockResolvedValue({ pendingInviteCount: 1 });
    fetchReceivedNamedInvitesMock.mockResolvedValue([INVITE]);
  });

  afterEach(() => {
    act(() => {
      root.unmount();
    });
    container.remove();
    clearStoredSession();
  });

  async function renderPage() {
    await act(async () => {
      root.render(
        createElement(MemoryRouter, {
          initialEntries: ["/inviti"],
          children: createElement(AuthProvider, {
            children: createElement(Harness),
          }),
        }),
      );
    });
    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 0));
    });
  }

  it("azzera il badge dopo Accetta, senza ricaricare la pagina", async () => {
    acceptReceivedNamedInviteMock.mockResolvedValue({ ...INVITE, status: "accepted" });
    await renderPage();

    expect(badgeText(container)).toBe("1");
    expect(container.querySelector('[data-testid="received-invites-list"]')).not.toBeNull();

    fetchPendingInviteCountMock.mockResolvedValue({ pendingInviteCount: 0 });
    await act(async () => {
      buttonByLabel(container, "Accetta").click();
    });
    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 0));
    });

    expect(acceptReceivedNamedInviteMock).toHaveBeenCalledWith("token-123", "invite-1");
    expect(badgeText(container)).toBe("0");
    expect(container.textContent).toContain("Sei entrato in Amici del Bar.");
    expect(container.querySelector('[data-testid="received-invites-list"]')).toBeNull();
  });

  it("azzera il badge anche dopo Rifiuta", async () => {
    declineReceivedNamedInviteMock.mockResolvedValue({ ...INVITE, status: "declined" });
    await renderPage();
    expect(badgeText(container)).toBe("1");

    fetchPendingInviteCountMock.mockResolvedValue({ pendingInviteCount: 0 });
    await act(async () => {
      buttonByLabel(container, "Rifiuta").click();
    });
    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 0));
    });

    expect(declineReceivedNamedInviteMock).toHaveBeenCalledWith("token-123", "invite-1");
    expect(badgeText(container)).toBe("0");
    expect(container.textContent).toContain("Invito rifiutato.");
  });
});
