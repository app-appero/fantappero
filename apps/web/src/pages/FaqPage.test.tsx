import { ToastProvider } from "@fantappero/ui";
import { FAQ_GROUPS, faqItems } from "@fantappero/contracts";
import { act, createElement } from "react";
import { createRoot, type Root } from "react-dom/client";
import { renderToStaticMarkup } from "react-dom/server";
import { afterEach, beforeEach, describe, expect, it } from "vitest";

import stylesCss from "../styles.css?raw";
import { AuthProvider } from "../auth/AuthContext";
import { MemoryRouter } from "../router/simpleRouter";
import { AppRoutes } from "../routes";
import { FaqPage } from "./FaqPage";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

function faqAt(entry = "/domande-frequenti") {
  return createElement(MemoryRouter, { initialEntries: [entry], children: createElement(FaqPage) });
}

function sidebarHrefs(html: string): string[] {
  const start = html.indexOf('data-testid="sidebar-nav"');
  expect(start).toBeGreaterThan(-1);
  const sidebar = html.slice(start, html.indexOf("</nav>", start));
  return [...sidebar.matchAll(/href="([^"]+)"/g)].map((match) => match[1] ?? "");
}

describe("FaqPage — Domande frequenti 1.4", () => {
  let container: HTMLDivElement;
  let root: Root;

  beforeEach(() => {
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);
  });

  afterEach(() => {
    act(() => root.unmount());
    container.remove();
  });

  it("mostra titolo, percorso «Aiuto», i quattro gruppi con un titolo e tutte le domande chiuse", () => {
    act(() => root.render(faqAt()));
    expect(container.querySelector("h1")?.textContent).toBe("Domande frequenti");
    expect(container.querySelector(".fa-breadcrumb")?.textContent).toContain("Aiuto");
    expect(container.textContent).toContain("Tocca una domanda per aprirla.");

    const groupTitles = [...container.querySelectorAll("h2.fa-faq__group-title")].map(
      (heading) => heading.textContent,
    );
    expect(groupTitles).toEqual(FAQ_GROUPS.map((group) => group.title));
    expect(groupTitles).toEqual(["Turni", "Calendario", "Ruoli", "Formazione"]);

    const buttons = [...container.querySelectorAll<HTMLButtonElement>("h3 > button.fa-faq__toggle")];
    expect(buttons.map((button) => button.querySelector(".fa-faq__question-text")?.textContent)).toEqual(
      faqItems().map((item) => item.question),
    );
    for (const button of buttons) {
      expect(button.getAttribute("aria-expanded")).toBe("false");
      const panel = document.getElementById(button.getAttribute("aria-controls") ?? "");
      expect(panel?.hidden).toBe(true);
    }
  });

  it("apre e richiude una risposta senza toccare le altre", () => {
    act(() => root.render(faqAt()));
    const toggle = container.querySelector<HTMLButtonElement>('[data-testid="faq-toggle-esubero"]')!;
    const answer = container.querySelector<HTMLDivElement>('[data-testid="faq-answer-esubero"]')!;
    const other = container.querySelector<HTMLDivElement>('[data-testid="faq-answer-turno-saltato"]')!;

    act(() => toggle.click());
    expect(toggle.getAttribute("aria-expanded")).toBe("true");
    expect(answer.hidden).toBe(false);
    expect(answer.textContent).toContain("Puoi svincolarne uno o scambiarlo.");
    expect(toggle.textContent).toContain("−");
    expect(other.hidden).toBe(true);

    act(() => container.querySelector<HTMLButtonElement>('[data-testid="faq-toggle-turno-saltato"]')!.click());
    expect(answer.hidden).toBe(false);
    expect(other.hidden).toBe(false);

    act(() => toggle.click());
    expect(toggle.getAttribute("aria-expanded")).toBe("false");
    expect(answer.hidden).toBe(true);
    expect(toggle.textContent).toContain("+");
    expect(other.hidden).toBe(false);
  });

  it("il link diretto ?domanda=<id> apre subito quella risposta", () => {
    const html = renderToStaticMarkup(faqAt("/domande-frequenti?domanda=regola-75"));
    // Già al primo disegno, prima degli effetti: una sola risposta aperta.
    expect(html.match(/aria-expanded="true"/g)).toHaveLength(1);
    act(() => root.render(faqAt("/domande-frequenti?domanda=regola-75")));
    expect(
      container.querySelector('[data-testid="faq-toggle-regola-75"]')?.getAttribute("aria-expanded"),
    ).toBe("true");
    expect(container.querySelector<HTMLDivElement>('[data-testid="faq-answer-regola-75"]')?.hidden).toBe(false);
    expect(
      container.querySelector('[data-testid="faq-toggle-turno-saltato"]')?.getAttribute("aria-expanded"),
    ).toBe("false");
  });

  it("un link diretto a una domanda che non esiste lascia tutto chiuso", () => {
    act(() => root.render(faqAt("/domande-frequenti?domanda=non-esiste")));
    expect(container.querySelectorAll('[aria-expanded="true"]')).toHaveLength(0);
  });

  it("nel menù del fantallenatore «Domande frequenti» viene subito dopo «Segnala un problema»", () => {
    const html = renderToStaticMarkup(
      createElement(MemoryRouter, {
        initialEntries: ["/domande-frequenti?persona=member&stato=success"],
        children: createElement(ToastProvider, {
          children: createElement(AuthProvider, { children: createElement(AppRoutes) }),
        }),
      }),
    );
    expect(html).toContain('data-testid="faq-page"');
    const hrefs = sidebarHrefs(html);
    const feedback = hrefs.indexOf("/feedback");
    expect(feedback).toBeGreaterThan(-1);
    expect(hrefs[feedback + 1]).toBe("/domande-frequenti");
    expect(hrefs[feedback + 2]).toBe("/profilo");
  });

  it("ha il blocco CSS «Domande frequenti 1.4» prima delle regole per iPhone", () => {
    const block = stylesCss.indexOf("/* Domande frequenti 1.4 */");
    const iphone = stylesCss.indexOf("/* ══ iPhone: sito aggiunto alla schermata Home");
    expect(block).toBeGreaterThan(-1);
    expect(block).toBeLessThan(iphone);
    const toggle = /\.fa-faq__toggle\s*\{([^}]*)\}/.exec(stylesCss)?.[1] ?? "";
    expect(toggle).toContain("min-height: 44px");
    expect(stylesCss).toMatch(/\.fa-faq__toggle:focus-visible\s*\{[^}]*outline: 2px solid/);
  });
});
