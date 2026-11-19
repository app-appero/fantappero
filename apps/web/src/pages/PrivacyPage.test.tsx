import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { renderToStaticMarkup } from "react-dom/server";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { PRIVACY_CONTACT_EMAIL } from "@fantappero/contracts";

import stylesCss from "../styles.css?raw";
import { PrivacyPage } from "./PrivacyPage";
import { BrowserRouter, MemoryRouter } from "../router/simpleRouter";

describe("PrivacyPage", () => {
  it("mostra versione, contatto e tutte le sezioni dell'informativa", () => {
    const html = renderToStaticMarkup(
      <MemoryRouter initialEntries={["/privacy"]}>
        <PrivacyPage />
      </MemoryRouter>,
    );
    expect(html).toContain('data-testid="privacy-page"');
    expect(html).toContain("2026-11");
    expect(html).toContain(PRIVACY_CONTACT_EMAIL);
    for (const id of ["dati", "finalita", "diritti", "eta"]) {
      expect(html).toContain(`data-testid="privacy-section-${id}"`);
    }
    expect(html).toContain("Segnalazioni");
    expect(html).toContain("Google");
  });

  it("ha i margini laterali e la larghezza massima definiti nel foglio di stile", () => {
    // Le classi fa-privacy* non erano definite da nessuna parte: testo attaccato ai bordi.
    const rule = /\.fa-privacy\s*\{([^}]*)\}/.exec(stylesCss)?.[1] ?? "";
    expect(rule).toContain("padding-inline: var(--fa-space-md)");
    expect(rule).toContain("background: var(--fa-color-background)");
    expect(rule).toContain("color: var(--fa-color-foreground)");
    const article = /\.fa-privacy__article\s*\{([^}]*)\}/.exec(stylesCss)?.[1] ?? "";
    expect(article).toContain("max-width: 46rem");
    expect(article).toContain("margin-inline: auto");
  });
});

describe("PrivacyPage — «← Indietro»", () => {
  let container: HTMLDivElement;
  let root: Root;

  function mockHistoryLength(length: number) {
    vi.spyOn(window.history, "length", "get").mockReturnValue(length);
  }

  async function renderAndClickBack() {
    await act(async () => {
      root.render(
        <BrowserRouter>
          <PrivacyPage />
        </BrowserRouter>,
      );
    });
    const back = container.querySelector<HTMLAnchorElement>('[data-testid="privacy-back"]');
    expect(back?.getAttribute("href")).toBe("/accedi");
    await act(async () => {
      back?.dispatchEvent(new MouseEvent("click", { bubbles: true, cancelable: true, button: 0 }));
    });
  }

  beforeEach(() => {
    window.history.replaceState(null, "", "/privacy");
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);
  });

  afterEach(() => {
    act(() => root.unmount());
    container.remove();
    vi.restoreAllMocks();
  });

  it("torna alla pagina precedente quando c'è", async () => {
    mockHistoryLength(3);
    const back = vi.spyOn(window.history, "back").mockImplementation(() => undefined);
    await renderAndClickBack();
    expect(back).toHaveBeenCalledTimes(1);
    expect(window.location.pathname).toBe("/privacy");
  });

  it("senza pagina precedente (link aperto da fuori) porta all'accesso", async () => {
    mockHistoryLength(1);
    const back = vi.spyOn(window.history, "back").mockImplementation(() => undefined);
    await renderAndClickBack();
    expect(back).not.toHaveBeenCalled();
    expect(window.location.pathname).toBe("/accedi");
  });
});
