import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { UiStatePanel } from "./UiStatePanel.js";

describe("UiStatePanel", () => {
  const states = ["loading", "empty", "error", "success", "forbidden"] as const;

  it.each(states)("renders %s state with test id", (state) => {
    const html = renderToStaticMarkup(
      createElement(UiStatePanel, {
        state,
        title: "Titolo",
        message: "Messaggio",
      }),
    );
    expect(html).toContain(`data-ui-state="${state}"`);
    expect(html).toContain(`data-testid="ui-state-${state}"`);
    expect(html).toContain("Titolo");
    expect(html).toContain("Messaggio");
  });

  it("marks loading state as busy for assistive tech", () => {
    const html = renderToStaticMarkup(
      createElement(UiStatePanel, {
        state: "loading",
        title: "Caricamento",
        message: "Attendere…",
      }),
    );
    expect(html).toContain('aria-busy="true"');
    expect(html).toContain('aria-live="polite"');
  });
});
