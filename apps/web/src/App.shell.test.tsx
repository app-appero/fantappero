import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { AuthProvider } from "./auth/AuthContext";
import { AppRoutes } from "./routes";
import { MemoryRouter } from "./router/simpleRouter";
import { ThemeProvider } from "./theme/ThemeProvider";

function renderShellAt(path: string, search = "") {
  return renderToStaticMarkup(
    createElement(MemoryRouter, {
      initialEntries: [`${path}${search}`],
      children: createElement(ThemeProvider, {
        children: createElement(AuthProvider, {
          children: createElement(AppRoutes),
        }),
      }),
    }),
  );
}

describe("App responsive shell (EPUI-05)", () => {
  it("exposes skip link and main landmark on member routes", () => {
    const html = renderShellAt("/turni", "?persona=admin&stato=success");
    expect(html).toContain('href="#main-content"');
    expect(html).toContain("Salta al contenuto principale");
    expect(html).toContain('id="main-content"');
  });

  it("exposes skip link on admin routes", () => {
    const html = renderShellAt("/admin", "?persona=operator&stato=success");
    expect(html).toContain('href="#main-content"');
    expect(html).toContain('data-surface="admin"');
  });

  it("omits app shell on auth routes", () => {
    const html = renderShellAt("/accedi", "?stato=success");
    expect(html).not.toContain('data-testid="app-shell"');
    expect(html).not.toContain("Salta al contenuto principale");
  });

  it("renders empty leagues state with create action", () => {
    const html = renderShellAt("/leghe", "?persona=admin&stato=empty");
    expect(html).toContain('data-testid="leagues-empty"');
    expect(html).toContain("Crea lega");
  });

  it("renders wireframe error state with retry affordance", () => {
    const html = renderShellAt("/mercato", "?persona=admin&stato=error");
    expect(html).toContain('data-testid="wireframe-market-error"');
    expect(html).toContain("Ricarica");
  });

  it("renders forbidden state on protected route for member persona", () => {
    const html = renderShellAt("/lega/amministrazione", "?persona=member&stato=success");
    expect(html).toContain('data-testid="route-forbidden"');
  });

  it("renders not-found placeholder outside the shell", () => {
    const html = renderShellAt("/percorso-sconosciuto");
    expect(html).toContain('data-testid="not-found"');
    expect(html).not.toContain('data-testid="app-shell"');
  });

  it("includes responsive shell structure for mobile and desktop nav", () => {
    const html = renderShellAt("/rosa", "?persona=admin&stato=success");
    expect(html).toContain('data-testid="sidebar-nav"');
    expect(html).toContain('data-testid="bottom-nav"');
  });
});
