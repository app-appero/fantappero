import { FAQ_HELP, faqHelpItem } from "@fantappero/contracts";
import { act, createElement } from "react";
import { createRoot, type Root } from "react-dom/client";
import { renderToStaticMarkup } from "react-dom/server";
import { afterEach, beforeEach, describe, expect, it } from "vitest";

import stylesCss from "../styles.css?raw";
import { FaqPage } from "../pages/FaqPage";
import { BrowserRouter, MemoryRouter, useLocation } from "../router/simpleRouter";
import { FaqHelpButton } from "./FaqHelpButton";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

/** Il «?» e, quando il link «Tutte le domande frequenti» porta lì, la pagina delle domande. */
function HelpOrFaq() {
  const { pathname } = useLocation();
  return pathname === "/domande-frequenti"
    ? createElement(FaqPage)
    : createElement("p", null, "Stato: Turno saltato ", createElement(FaqHelpButton, { faqId: FAQ_HELP.skippedTurn }));
}

function rule(selector: string): string {
  const escaped = selector.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  return new RegExp(`(?:^|\\n)${escaped}\\s*\\{([^}]*)\\}`).exec(stylesCss)?.[1] ?? "";
}

describe("FaqHelpButton — il «?» delle Domande frequenti 1.4", () => {
  let container: HTMLDivElement;
  let root: Root;

  beforeEach(() => {
    window.history.replaceState(null, "", "/turni?tab=europei");
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);
  });

  afterEach(() => {
    act(() => root.unmount());
    container.remove();
    window.history.replaceState(null, "", "/");
  });

  const dialog = () => document.body.querySelector<HTMLElement>('[role="dialog"]');

  it("è un pulsante con il nome della domanda senza virgolette e il cerchio nascosto al lettore", () => {
    const html = renderToStaticMarkup(
      createElement(MemoryRouter, {
        initialEntries: ["/turni"],
        children: createElement(FaqHelpButton, { faqId: FAQ_HELP.skippedTurn }),
      }),
    );
    expect(html).toContain('aria-label="Perché un turno è saltato?"');
    expect(html).toContain('aria-haspopup="dialog"');
    expect(html).toContain('aria-expanded="false"');
    expect(html).toContain('<span class="fa-faq-help__glyph" aria-hidden="true">?</span>');
    // Chiuso: nessuna finestra, nemmeno nel disegno lato server.
    expect(html).not.toContain('role="dialog"');
  });

  it("un tocco apre la risposta giusta, con il link alla pagina e «Ho capito» che chiude", () => {
    act(() => root.render(createElement(BrowserRouter, { children: createElement(HelpOrFaq) })));
    const button = container.querySelector<HTMLButtonElement>('[data-testid="faq-help-turno-saltato"]')!;
    expect(button.getAttribute("aria-label")).toBe("Perché un turno è saltato?");

    act(() => button.click());
    const opened = dialog();
    expect(opened).not.toBeNull();
    expect(button.getAttribute("aria-expanded")).toBe("true");
    // La finestra è in fondo a <body>, non dentro il <p> della scritta.
    expect(container.contains(opened)).toBe(false);
    expect(opened?.classList.contains("fa-faq-sheet")).toBe(true);
    const title = document.getElementById(opened?.getAttribute("aria-labelledby") ?? "");
    expect(title?.textContent).toBe("Perché un turno è «saltato»?");
    const item = faqHelpItem(FAQ_HELP.skippedTurn);
    expect(
      [...opened!.querySelectorAll('[data-testid="faq-help-turno-saltato-answer"] p')].map((p) => p.textContent),
    ).toEqual([...item.answer]);
    expect(opened?.textContent).toContain("almeno 9 titolari (è la regola standard");
    const link = opened!.querySelector<HTMLAnchorElement>('[data-testid="faq-help-turno-saltato-all"]')!;
    expect(link.getAttribute("href")).toBe("/domande-frequenti?domanda=turno-saltato");
    expect(link.textContent?.replace(/\s/g, " ")).toBe("Tutte le domande frequenti ›");
    // Il dialogo prende il fuoco: il lettore di schermo legge subito la domanda.
    expect(document.activeElement).toBe(opened);

    act(() => opened!.querySelector<HTMLButtonElement>('[data-testid="faq-help-turno-saltato-close"]')!.click());
    expect(dialog()).toBeNull();
    expect(button.getAttribute("aria-expanded")).toBe("false");
    // Il fuoco torna sul «?».
    expect(document.activeElement).toBe(button);
  });

  it("si chiude con Esc e con il velo scuro", () => {
    act(() => root.render(createElement(BrowserRouter, { children: createElement(HelpOrFaq) })));
    const button = container.querySelector<HTMLButtonElement>('[data-testid="faq-help-turno-saltato"]')!;

    act(() => button.click());
    act(() => {
      dialog()!.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true }));
    });
    expect(dialog()).toBeNull();

    act(() => button.click());
    act(() => document.body.querySelector<HTMLButtonElement>(".fa-modal__backdrop")!.click());
    expect(dialog()).toBeNull();
  });

  it("«Tutte le domande frequenti» porta alla pagina con quella risposta aperta", () => {
    act(() => root.render(createElement(BrowserRouter, { children: createElement(HelpOrFaq) })));
    act(() => container.querySelector<HTMLButtonElement>('[data-testid="faq-help-turno-saltato"]')!.click());
    act(() => {
      dialog()!
        .querySelector<HTMLAnchorElement>('[data-testid="faq-help-turno-saltato-all"]')!
        .dispatchEvent(new MouseEvent("click", { bubbles: true, cancelable: true, button: 0 }));
    });
    expect(`${window.location.pathname}${window.location.search}`).toBe("/domande-frequenti?domanda=turno-saltato");
    expect(dialog()).toBeNull();
    expect(container.querySelector('[data-testid="faq-page"]')).not.toBeNull();
    expect(
      container.querySelector('[data-testid="faq-toggle-turno-saltato"]')?.getAttribute("aria-expanded"),
    ).toBe("true");
  });

  it("apre anche le risposte su esubero e blocco della formazione", () => {
    for (const [faqId, label] of [
      [FAQ_HELP.surplus, "Ho un giocatore in esubero: cosa faccio?"],
      [FAQ_HELP.lineupLock, "Quando si blocca la formazione?"],
    ] as const) {
      act(() =>
        root.render(
          createElement(MemoryRouter, { initialEntries: ["/rosa"], children: createElement(FaqHelpButton, { faqId }) }),
        ),
      );
      const button = container.querySelector<HTMLButtonElement>(`[data-testid="faq-help-${faqId}"]`)!;
      expect(button.getAttribute("aria-label")).toBe(label);
      act(() => button.click());
      expect(dialog()?.textContent).toContain(faqHelpItem(faqId).answer[0]);
      expect(dialog()?.querySelector("a")?.getAttribute("href")).toBe(`/domande-frequenti?domanda=${faqId}`);
      act(() => dialog()!.querySelector<HTMLButtonElement>(`[data-testid="faq-help-${faqId}-close"]`)!.click());
    }
  });

  it("area di tocco di 44px, fuoco visibile e risposta dal basso sul telefono", () => {
    const button = rule(".fa-faq-help");
    expect(button).toContain("min-width: 44px");
    expect(button).toContain("min-height: 44px");
    expect(rule(".fa-faq-help__glyph")).toContain("width: 22px");
    expect(stylesCss).toMatch(/\.fa-faq-help:focus-visible \.fa-faq-help__glyph\s*\{[^}]*outline: 2px solid/);
    expect(rule(".fa-faq-sheet__all")).toContain("min-height: 44px");
    const phone = stylesCss.slice(stylesCss.indexOf("/* Telefono: la risposta sale dal basso"));
    expect(phone).toMatch(/@media \(max-width: 640px\)\s*\{\s*\.fa-modal:has\(> \.fa-faq-sheet\)\s*\{[^}]*align-items: flex-end;/);
    expect(phone).toMatch(/\.fa-modal__dialog\.fa-faq-sheet\s*\{[^}]*width: 100%;[^}]*border-radius: 18px 18px 0 0;/);
    // Il blocco sta prima delle regole per iPhone, come quello della pagina.
    expect(stylesCss.indexOf("/* «?» delle Domande frequenti 1.4 */")).toBeLessThan(
      stylesCss.indexOf("/* ══ iPhone: sito aggiunto alla schermata Home"),
    );
  });
});
