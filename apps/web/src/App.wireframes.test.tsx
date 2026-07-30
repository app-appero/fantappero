import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "./router/simpleRouter";
import { describe, expect, it } from "vitest";
import { AuthProvider } from "./auth/AuthContext";
import { AppRoutes } from "./routes";
import { WIREFRAME_CATALOG, WIREFRAME_STATES } from "./wireframes/catalog";

function renderAt(path: string, search = "") {
  return renderToStaticMarkup(
    createElement(MemoryRouter, {
      initialEntries: [`${path}${search}`],
      children: createElement(AuthProvider, {
        children: createElement(AppRoutes),
      }),
    }),
  );
}

function wireframeSearch(route: string, state: string): string {
  const params = new URLSearchParams({ stato: state });
  if (route === "/lega/amministrazione") {
    params.set("persona", "admin");
  }
  return `?${params.toString()}`;
}

describe("EPUI-04 wireframes", () => {
  for (const screen of WIREFRAME_CATALOG) {
    if (screen.route.startsWith("/admin")) {
      continue;
    }

    it(`renders ${screen.id} success wireframe at ${screen.route}`, () => {
      const html = renderAt(screen.route, wireframeSearch(screen.route, "success"));
      expect(html).toContain(`data-testid="wireframe-${screen.id}-success"`);
    });

    for (const state of WIREFRAME_STATES) {
      if (state === "success") {
        continue;
      }

      it(`renders ${screen.id} ${state} state at ${screen.route}`, () => {
        const html = renderAt(screen.route, wireframeSearch(screen.route, state));
        expect(html).toContain(`data-testid="wireframe-${screen.id}-${state}"`);
      });
    }
  }

  it("renders auth page without app shell", () => {
    const html = renderAt("/accedi", "?stato=success");
    expect(html).toContain('data-testid="auth-form-layout"');
    expect(html).toContain('data-testid="brand-logo"');
    expect(html).toContain("FantApperò");
    expect(html).toContain("fa-surface-pitch");
    expect(html).not.toContain('data-testid="app-shell"');
  });

  it("renders classifica standings table on success", () => {
    const html = renderAt("/classifica", "?stato=success");
    expect(html).toContain('data-testid="standings-table"');
  });

  it("renders auction panel for member", () => {
    const html = renderAt("/asta", "?stato=success");
    expect(html).toContain('data-testid="auction-bid-panel"');
  });

  it("shows admin auction controls for admin persona", () => {
    const html = renderAt("/asta", "?persona=admin&stato=success");
    expect(html).toContain('data-testid="wireframe-region-auction-admin"');
  });

  it("renders wireframe meta panel when meta=1", () => {
    const html = renderAt("/mercato", "?stato=success&meta=1");
    expect(html).toContain('data-testid="wireframe-meta-panel"');
    expect(html).toContain("CTA primaria");
  });

  it("renders wireframes dev hub", () => {
    const html = renderAt("/dev/wireframes");
    expect(html).toContain("Hub di validazione EPUI-04");
    expect(html).toContain("/classifica?stato=empty");
  });

  it("renders operator panel with admin surface", () => {
    const html = renderAt("/admin", "?persona=operator&stato=success");
    expect(html).toContain('data-surface="admin"');
    expect(html).toContain('data-testid="wireframe-operator-panel-success"');
  });
});
