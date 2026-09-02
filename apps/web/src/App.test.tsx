import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "./router/simpleRouter";
import { describe, expect, it } from "vitest";
import { AuthProvider } from "./auth/AuthContext";
import { AppRoutes } from "./routes";

describe("App routing entry", () => {
  it("redirects root to leagues", () => {
    const html = renderToStaticMarkup(
      createElement(MemoryRouter, {
        initialEntries: ["/?persona=admin&stato=success"],
        children: createElement(AuthProvider, {
          children: createElement(AppRoutes),
        }),
      }),
    );
    expect(html).toContain('data-testid="league-home-content"');
  });
});
