import type { FantasyCoachProfile, LeagueMember, UserProfile } from "@fantappero/contracts";
import { act, createElement, type ReactElement } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { fetchLeagueMembers } from "../api/leagues";
import { fetchProfile } from "../api/profile";
import { CoachProfilePanel, ManagerDirectory } from "../components/ManagerDirectory";
import { MemoryRouter } from "../router/simpleRouter";
import { LeagueMembersPanel } from "./LeagueMembersPanel";
import { ProfilePage } from "./ProfilePage";

/**
 * QA 20-21/11: un avatar che risponde 404 restava un'immagine rotta in Partecipanti,
 * Fantallenatori (elenco e profilo) e Profilo. Ora, come in classifica e nelle sfide,
 * al posto dell'immagine restano le iniziali.
 */

const BROKEN = "https://cdn.example.test/media/avatars/404.png?v=1";

vi.mock("../auth/AuthContext", async (importOriginal) => {
  const original = await importOriginal<typeof import("../auth/AuthContext")>();
  return {
    ...original,
    useAuth: () => ({
      isDemoMode: false,
      user: { id: "user-me", displayName: "Marco Rossi", globalRole: "member" },
      updateDisplayName: vi.fn(),
      logout: vi.fn(),
    }),
  };
});

vi.mock("../auth/sessionStorage", async (importOriginal) => {
  const original = await importOriginal<typeof import("../auth/sessionStorage")>();
  return { ...original, loadStoredSession: () => ({ accessToken: "token-finto" }) };
});

vi.mock("../api/leagues", async (importOriginal) => {
  const original = await importOriginal<typeof import("../api/leagues")>();
  return { ...original, fetchLeagueMembers: vi.fn() };
});

vi.mock("../api/profile", () => ({
  fetchProfile: vi.fn(),
  updateProfile: vi.fn(),
  uploadAvatar: vi.fn(),
  removeAvatar: vi.fn(),
  updateInviteAvailability: vi.fn(),
  recordPolicyConsent: vi.fn(),
}));

vi.mock("../api/notifications", async (importOriginal) => {
  const original = await importOriginal<typeof import("../api/notifications")>();
  return { ...original, fetchNotificationPreferences: vi.fn(() => new Promise(() => {})) };
});

describe("Avatar in 404: restano le iniziali (Partecipanti, Fantallenatori, Profilo)", () => {
  let container: HTMLDivElement;
  let root: Root;

  async function render(element: ReactElement) {
    await act(async () => {
      root.render(createElement(MemoryRouter, { initialEntries: ["/"], children: element }));
    });
  }

  async function failImages(selector = "img") {
    const images = [...container.querySelectorAll<HTMLImageElement>(selector)];
    expect(images.length).toBeGreaterThan(0);
    await act(async () => {
      for (const image of images) {
        image.dispatchEvent(new Event("error"));
      }
    });
  }

  beforeEach(() => {
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);
  });

  afterEach(() => {
    act(() => root.unmount());
    container.remove();
    vi.clearAllMocks();
  });

  it("Partecipanti: la foto che non si carica lascia le iniziali nel cerchio", async () => {
    const members: LeagueMember[] = [
      {
        userId: "user-giulia",
        displayName: "Giulia Rossi",
        email: null,
        avatarUrl: BROKEN,
        userType: "human",
        role: "member",
        joinedAt: "2026-08-02T10:00:00Z",
      },
    ];
    vi.mocked(fetchLeagueMembers).mockResolvedValue(members);

    await render(createElement(LeagueMembersPanel, { leagueId: "lega-1", isDemoMode: false, search: "" }));

    const avatar = container.querySelector(".fa-member-list__avatar");
    expect(avatar?.querySelector(`img[src="${BROKEN}"]`)).not.toBeNull();

    await failImages(".fa-member-list__avatar img");

    expect(avatar?.querySelector("img")).toBeNull();
    expect(avatar?.textContent).toBe("GR");
  });

  it("Fantallenatori: nell'elenco la foto in 404 lascia le iniziali", async () => {
    await render(createElement(ManagerDirectory, { leagueId: "demo-league", isDemoMode: true, search: "" }));

    const row = container.querySelector('[data-testid="manager-open-manager-lucia"]')?.closest("li");
    expect(row?.querySelector("img.fa-manager-directory__avatar")).not.toBeNull();

    await failImages("img.fa-manager-directory__avatar");

    expect(container.querySelector("img.fa-manager-directory__avatar")).toBeNull();
    expect(row?.querySelector(".fa-manager-directory__avatar")?.textContent).toBe("LB");
  });

  it("Fantallenatori: nel profilo la foto in 404 lascia le iniziali", async () => {
    const profile = {
      userId: "coach-1",
      displayName: "Lucia Bianchi",
      nickname: null,
      email: null,
      avatarUrl: BROKEN,
      userType: "human",
      availableForInvites: true,
      namedInviteStatus: null,
      memberSince: "03/2025",
      concludedLeagues: 0,
      bestPosition: null,
      historySummary: "",
      placements: [],
      placementsPage: 1,
      placementsPageSize: 20,
      placementsTotal: 0,
    } as FantasyCoachProfile;

    await render(createElement(CoachProfilePanel, { profile, onClose: () => {} }));
    expect(container.querySelector(`img.fa-coach-profile__avatar[src="${BROKEN}"]`)).not.toBeNull();

    await failImages();

    expect(container.querySelector("img")).toBeNull();
    expect(container.querySelector(".fa-coach-profile__avatar")?.textContent).toBe("LB");
  });

  it("Profilo: l'avatar in 404 lascia le iniziali al posto dell'immagine", async () => {
    const profile: UserProfile = {
      email: "marco@example.com",
      displayName: "Marco Rossi",
      avatarUrl: BROKEN,
      language: "it",
      timezone: "Europe/Rome",
      notificationsEmail: true,
      notificationsPush: true,
      quietHoursStartHour: null,
      quietHoursEndHour: null,
      policyConsentAt: "2026-01-15T10:00:00.000Z",
      policyVersion: "2026-01",
      currentPolicyVersion: "2026-01",
      userType: "human",
      availableForInvites: true,
    };
    vi.mocked(fetchProfile).mockResolvedValue(profile);

    await render(createElement(ProfilePage));
    const image = container.querySelector('[data-testid="profile-avatar-image"]');
    expect(image?.getAttribute("src")).toBe(BROKEN);
    expect(image?.className).toBe("fa-profile-avatar__image");

    await failImages('[data-testid="profile-avatar-image"]');

    expect(container.querySelector('[data-testid="profile-avatar-image"]')).toBeNull();
    expect(container.querySelector('[data-testid="profile-avatar-placeholder"]')?.textContent).toBe("MR");
  });
});
