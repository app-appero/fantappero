import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { AppErrorBoundary } from "./AppErrorBoundary";

describe("AppErrorBoundary (EPUI-05)", () => {
  it("derives error state from thrown errors", () => {
    expect(AppErrorBoundary.getDerivedStateFromError()).toEqual({ hasError: true });
  });

  it("renders children when no error occurred", () => {
    const html = renderToStaticMarkup(
      createElement(AppErrorBoundary, null, createElement("p", null, "contenuto ok")),
    );
    expect(html).toContain("contenuto ok");
    expect(html).not.toContain('data-testid="app-error-boundary"');
  });
});
