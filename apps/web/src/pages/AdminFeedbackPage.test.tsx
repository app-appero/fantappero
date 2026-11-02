import type { FeedbackAdminList, FeedbackAdminReport } from "@fantappero/contracts";
import { act, createElement } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const fetchAdminFeedbackMock = vi.fn();
const updateAdminFeedbackMock = vi.fn();
const impersonateUserMock = vi.fn();
const startImpersonationMock = vi.fn();
const navigateMock = vi.fn();

vi.mock("../api/feedback", () => ({
  fetchAdminFeedback: (...args: unknown[]) => fetchAdminFeedbackMock(...args),
  updateAdminFeedback: (...args: unknown[]) => updateAdminFeedbackMock(...args),
}));
vi.mock("../api/admin", () => ({
  impersonateUser: (...args: unknown[]) => impersonateUserMock(...args),
}));
vi.mock("../api/client", () => {
  class ApiError extends Error {
    constructor(
      message: string,
      readonly status: number,
      readonly code: string,
    ) {
      super(message);
    }
  }
  return { ApiError, buildApiUrl: (path: string) => `https://api.example.test${path}` };
});
vi.mock("../auth/AuthContext", () => ({
  useAuth: () => ({ user: { id: "op-1" }, startImpersonation: startImpersonationMock }),
  getApiErrorMessage: (error: unknown, fallback: string) =>
    error instanceof Error ? error.message : fallback,
}));
vi.mock("../router/simpleRouter", async () => {
  const actual = await vi.importActual<typeof import("../router/simpleRouter")>("../router/simpleRouter");
  return { ...actual, useNavigate: () => navigateMock };
});

import { clearStoredSession, saveStoredSession } from "../auth/sessionStorage";
import { MemoryRouter } from "../router/simpleRouter";
import { AdminFeedbackPage } from "./AdminFeedbackPage";

function report(overrides: Partial<FeedbackAdminReport> = {}): FeedbackAdminReport {
  return {
    id: "r1",
    category: "bug",
    message: "Il pulsante salva non risponde",
    status: "new",
    createdAt: "2026-11-02T10:00:00Z",
    authorUserId: "u1",
    authorName: "Mario",
    authorEmail: "mario@example.com",
    pageContext: "/formazione",
    platform: "web",
    appVersion: "0.0.0",
    userAgent: "Mozilla/5.0",
    operatorNote: null,
    handledAt: null,
    attachments: [
      { id: "a1", kind: "image", contentType: "image/png", sizeBytes: 10, url: "/feedback/media/a1?token=t1" },
      { id: "a2", kind: "video", contentType: "video/mp4", sizeBytes: 10, url: "/feedback/media/a2?token=t2" },
    ],
    ...overrides,
  };
}

function listing(items: FeedbackAdminReport[], newCount = items.length): FeedbackAdminList {
  return { items, total: items.length, newCount, page: 1, pageSize: 20 };
}

describe("AdminFeedbackPage — pannello operatore", () => {
  let container: HTMLDivElement;
  let root: Root;
  const q = (testId: string) => container.querySelector(`[data-testid="${testId}"]`) as HTMLElement | null;

  async function render() {
    await act(async () => {
      root.render(createElement(MemoryRouter, { initialEntries: ["/admin/feedback"], children: createElement(AdminFeedbackPage) }));
    });
  }

  beforeEach(() => {
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);
    fetchAdminFeedbackMock.mockReset();
    updateAdminFeedbackMock.mockReset();
    impersonateUserMock.mockReset();
    startImpersonationMock.mockReset();
    navigateMock.mockReset();
    saveStoredSession({
      accessToken: "op-token",
      refreshToken: "refresh",
      user: { id: "op-1", displayName: "Operatore", globalRole: "global_operator" },
    });
  });

  afterEach(() => {
    act(() => root.unmount());
    container.remove();
    clearStoredSession();
  });

  it("mostra autore, contesto, allegati con link firmati e conteggio da leggere", async () => {
    fetchAdminFeedbackMock.mockResolvedValue(listing([report()]));
    await render();
    expect(fetchAdminFeedbackMock).toHaveBeenCalledWith("op-token", { status: undefined, page: 1 });
    const card = q("feedback-admin-r1")!;
    expect(card.textContent).toContain("Il pulsante salva non risponde");
    expect(card.textContent).toContain("Mario · mario@example.com");
    expect(card.textContent).toContain("/formazione");
    expect(card.querySelector("img")?.getAttribute("src")).toBe("https://api.example.test/feedback/media/a1?token=t1");
    expect(card.querySelector("video")?.getAttribute("src")).toBe("https://api.example.test/feedback/media/a2?token=t2");
    expect(q("feedback-admin-new-count")?.textContent).toBe("1 da leggere");
  });

  it("cambia lo stato con un clic e ricarica l'elenco", async () => {
    fetchAdminFeedbackMock.mockResolvedValueOnce(listing([report()]));
    updateAdminFeedbackMock.mockResolvedValue(report({ status: "resolved" }));
    fetchAdminFeedbackMock.mockResolvedValueOnce(listing([report({ status: "resolved" })], 0));
    await render();
    await act(async () => {
      q("feedback-admin-resolved-r1")!.click();
    });
    expect(updateAdminFeedbackMock).toHaveBeenCalledWith("op-token", "r1", {
      status: "resolved",
      operatorNote: "",
    });
    expect(q("feedback-admin-new-count")?.textContent).toBe("Nessuna segnalazione da leggere");
    // «Segna come risolta» non è più proposto per una segnalazione già risolta.
    expect(q("feedback-admin-resolved-r1")).toBeNull();
    expect(q("feedback-admin-new-r1")).not.toBeNull();
  });

  it("mostra lo stato vuoto e gli errori di caricamento", async () => {
    fetchAdminFeedbackMock.mockResolvedValue(listing([]));
    await render();
    expect(q("feedback-admin-empty")).not.toBeNull();

    fetchAdminFeedbackMock.mockRejectedValue(new Error("Non autorizzato"));
    await act(async () => {
      container.querySelector<HTMLButtonElement>(".fa-feedback-admin__toolbar button")!.click();
    });
    expect(q("feedback-admin-error")?.textContent).toContain("Non autorizzato");
  });

  it("segnala un allegato scaduto e invita ad aggiornare", async () => {
    fetchAdminFeedbackMock.mockResolvedValue(listing([report()]));
    await render();
    await act(async () => {
      q("feedback-admin-r1")!.querySelector("img")!.dispatchEvent(new Event("error"));
    });
    expect(q("feedback-admin-expired")).not.toBeNull();
  });

  it("impersona l'autore dopo la conferma e apre la pagina della segnalazione", async () => {
    fetchAdminFeedbackMock.mockResolvedValue(listing([report({ pageContext: "/lega/amministrazione" })]));
    const session = { accessToken: "imp-token", refreshToken: "r", user: { id: "u1" } };
    impersonateUserMock.mockResolvedValue(session);
    await render();

    await act(async () => {
      q("feedback-admin-impersonate-r1")!.click();
    });
    // Prima serve la conferma: nessuna chiamata finché non si conferma.
    expect(impersonateUserMock).not.toHaveBeenCalled();
    expect(document.body.textContent).toContain("Accederai come Mario");

    await act(async () => {
      (document.querySelector('[data-testid="feedback-admin-impersonate-confirm"]') as HTMLElement).click();
    });
    expect(impersonateUserMock).toHaveBeenCalledWith("op-token", "u1");
    expect(startImpersonationMock).toHaveBeenCalledWith(session);
    expect(navigateMock).toHaveBeenCalledWith("/lega/amministrazione");
  });

  it("ripiega sulle leghe se il contesto non è una pagina interna", async () => {
    fetchAdminFeedbackMock.mockResolvedValue(listing([report({ pageContext: "Formation" })]));
    impersonateUserMock.mockResolvedValue({});
    await render();
    await act(async () => {
      q("feedback-admin-impersonate-r1")!.click();
    });
    await act(async () => {
      (document.querySelector('[data-testid="feedback-admin-impersonate-confirm"]') as HTMLElement).click();
    });
    expect(navigateMock).toHaveBeenCalledWith("/leghe");
  });

  it("non offre il pulsante per se stessi né per un utente eliminato", async () => {
    fetchAdminFeedbackMock.mockResolvedValue(
      listing([
        report({ id: "mine", authorUserId: "op-1" }),
        report({ id: "gone", authorUserId: "u9", authorEmail: "" }),
        report({ id: "ok", authorUserId: "u2" }),
      ]),
    );
    await render();
    expect(q("feedback-admin-impersonate-mine")).toBeNull();
    expect(q("feedback-admin-impersonate-gone")).toBeNull();
    expect(q("feedback-admin-impersonate-ok")).not.toBeNull();
  });

  it("mostra l'errore se l'impersonificazione non riesce", async () => {
    fetchAdminFeedbackMock.mockResolvedValue(listing([report()]));
    impersonateUserMock.mockRejectedValue(new Error("Utente non trovato"));
    await render();
    await act(async () => {
      q("feedback-admin-impersonate-r1")!.click();
    });
    await act(async () => {
      (document.querySelector('[data-testid="feedback-admin-impersonate-confirm"]') as HTMLElement).click();
    });
    expect(q("feedback-admin-impersonate-error")?.textContent).toContain("Utente non trovato");
    expect(navigateMock).not.toHaveBeenCalled();
  });
});
