import type { FeedbackReportSummary } from "@fantappero/contracts";
import { act, createElement } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const sendFeedbackMock = vi.fn();
const fetchMyFeedbackMock = vi.fn();

vi.mock("../api/feedback", () => ({
  sendFeedback: (...args: unknown[]) => sendFeedbackMock(...args),
  fetchMyFeedback: (...args: unknown[]) => fetchMyFeedbackMock(...args),
}));
vi.mock("../auth/AuthContext", () => ({
  useAuth: () => ({ isDemoMode: false }),
  getApiErrorMessage: (error: unknown, fallback: string) =>
    error instanceof Error ? error.message : fallback,
}));

import { clearStoredSession, saveStoredSession } from "../auth/sessionStorage";
import { MemoryRouter } from "../router/simpleRouter";
import { FeedbackPage } from "./FeedbackPage";

const GOOD = "Dopo aver salvato la formazione il pulsante resta grigio.";

function setValue(element: HTMLTextAreaElement | HTMLSelectElement, value: string) {
  const prototype = Object.getPrototypeOf(element) as object;
  const setter = Object.getOwnPropertyDescriptor(prototype, "value")?.set;
  act(() => {
    setter?.call(element, value);
    element.dispatchEvent(new Event("input", { bubbles: true }));
    element.dispatchEvent(new Event("change", { bubbles: true }));
  });
}

function pickFiles(input: HTMLInputElement, files: File[]) {
  Object.defineProperty(input, "files", { value: files, configurable: true });
  input.dispatchEvent(new Event("change", { bubbles: true }));
}

describe("FeedbackPage — segnalazione dell'utente", () => {
  let container: HTMLDivElement;
  let root: Root;

  const q = <T extends Element>(testId: string) =>
    container.querySelector(`[data-testid="${testId}"]`) as T | null;

  async function render() {
    await act(async () => {
      root.render(createElement(MemoryRouter, { initialEntries: ["/feedback"], children: createElement(FeedbackPage) }));
    });
  }

  async function submit() {
    await act(async () => {
      q<HTMLFormElement>("feedback-form")!.dispatchEvent(
        new Event("submit", { bubbles: true, cancelable: true }),
      );
    });
  }

  beforeEach(() => {
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);
    sendFeedbackMock.mockReset();
    fetchMyFeedbackMock.mockReset().mockResolvedValue([]);
    URL.createObjectURL = vi.fn(() => "blob:preview");
    URL.revokeObjectURL = vi.fn();
    saveStoredSession({
      accessToken: "token-123",
      refreshToken: "refresh-123",
      user: { id: "user-1", displayName: "Membro Test", globalRole: "member" },
    });
  });

  afterEach(() => {
    act(() => root.unmount());
    container.remove();
    clearStoredSession();
  });

  it("non invia un testo troppo breve", async () => {
    await render();
    setValue(q<HTMLTextAreaElement>("feedback-message")!, "non va");
    await submit();
    expect(q("feedback-error")?.textContent).toContain("almeno 10 caratteri");
    expect(sendFeedbackMock).not.toHaveBeenCalled();
  });

  it("invia testo, categoria e allegato, poi svuota il modulo", async () => {
    sendFeedbackMock.mockResolvedValue({ id: "r1" });
    await render();
    setValue(q<HTMLSelectElement>("feedback-form")!.querySelector("select")!, "suggerimento");
    setValue(q<HTMLTextAreaElement>("feedback-message")!, GOOD);
    const screenshot = new File([new Uint8Array(2048)], "schermata.png", { type: "image/png" });
    await act(async () => pickFiles(q<HTMLInputElement>("feedback-file-input")!, [screenshot]));
    expect(q("feedback-files")?.textContent).toContain("schermata.png");

    await submit();

    expect(sendFeedbackMock).toHaveBeenCalledTimes(1);
    const [token, input] = sendFeedbackMock.mock.calls[0] as [string, Record<string, unknown>];
    expect(token).toBe("token-123");
    expect(input).toMatchObject({ message: GOOD, category: "suggerimento", files: [screenshot] });
    expect(q("feedback-sent")).not.toBeNull();
    expect(q<HTMLTextAreaElement>("feedback-message")!.value).toBe("");
    expect(q("feedback-files")).toBeNull();
  });

  it("accetta un video e mostra l'avviso di caricamento", async () => {
    await render();
    const clip = new File([new Uint8Array(2048)], "clip.mp4", { type: "video/mp4" });
    await act(async () => pickFiles(q<HTMLInputElement>("feedback-file-input")!, [clip]));
    expect(q("feedback-files")?.textContent).toContain("Video");
    expect(q("feedback-error")).toBeNull();
  });

  it("rifiuta un formato non supportato senza aggiungerlo", async () => {
    await render();
    const pdf = new File([new Uint8Array(10)], "nota.pdf", { type: "application/pdf" });
    await act(async () => pickFiles(q<HTMLInputElement>("feedback-file-input")!, [pdf]));
    expect(q("feedback-error")?.textContent).toContain("formato non supportato");
    expect(q("feedback-files")).toBeNull();
  });

  it("rifiuta più di 3 allegati", async () => {
    await render();
    const image = (name: string) => new File([new Uint8Array(10)], name, { type: "image/png" });
    await act(async () =>
      pickFiles(q<HTMLInputElement>("feedback-file-input")!, [image("a.png"), image("b.png"), image("c.png"), image("d.png")]),
    );
    expect(q("feedback-error")?.textContent).toContain("al massimo 3");
  });

  it("mostra l'errore del server e conserva il testo scritto", async () => {
    sendFeedbackMock.mockRejectedValue(new Error("Hai inviato molte segnalazioni di recente."));
    await render();
    setValue(q<HTMLTextAreaElement>("feedback-message")!, GOOD);
    await submit();
    expect(q("feedback-error")?.textContent).toContain("molte segnalazioni");
    expect(q<HTMLTextAreaElement>("feedback-message")!.value).toBe(GOOD);
  });

  it("elenca le segnalazioni già inviate con il loro stato", async () => {
    const report: FeedbackReportSummary = {
      id: "r1",
      category: "bug",
      message: "Il voto non si vede",
      status: "in_review",
      createdAt: "2026-11-02T10:00:00Z",
      attachmentCount: 2,
    };
    fetchMyFeedbackMock.mockResolvedValue([report]);
    await render();
    expect(q("feedback-mine")?.textContent).toContain("Il voto non si vede");
    expect(q("feedback-mine")?.textContent).toContain("In lavorazione");
    expect(q("feedback-mine")?.textContent).toContain("2 allegati");
  });
});
