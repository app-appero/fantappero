import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { App } from "./App";

describe("App health page", () => {
  it("renders ok health status", () => {
    const html = renderToStaticMarkup(createElement(App));
    expect(html).toContain('data-testid="health-status"');
    expect(html).toContain(">ok<");
    expect(html).toContain("fantappero-web");
  });
});
