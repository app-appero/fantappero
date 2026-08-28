import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "./router/simpleRouter";
import { describe, expect, it } from "vitest";
import { AuthProvider } from "./auth/AuthContext";
import { AppRoutes } from "./routes";

function renderAt(path: string, search = "?persona=admin&stato=success") {
  return renderToStaticMarkup(
    createElement(MemoryRouter, {
      initialEntries: [`${path}${search.startsWith("?") ? search : `?${search}`}`],
      children: createElement(AuthProvider, {
        children: createElement(AppRoutes),
      }),
    }),
  );
}

/** Isola il markup della sidebar: le pagine possono contenere gli stessi link. */
function sidebarMarkup(html: string): string {
  const start = html.indexOf('data-testid="sidebar-nav"');
  expect(start).toBeGreaterThan(-1);
  const end = html.indexOf("</nav>", start);
  return html.slice(start, end);
}

describe("App navigation shell (EPUI-03)", () => {
  it("renders member app layout with sidebar and bottom nav on /turni", () => {
    const html = renderAt("/turni");
    expect(html).toContain('data-testid="app-shell"');
    expect(html).toContain('data-testid="sidebar-nav"');
    expect(html).toContain('data-testid="bottom-nav"');
    expect(html).toContain("Turni");
  });

  it("hides league admin link for default member persona", () => {
    const sidebar = sidebarMarkup(renderAt("/leghe", "?persona=member&stato=success"));
    expect(sidebar).not.toContain("Amministrazione lega");
    expect(sidebar).not.toContain('href="/lega/amministrazione"');
  });

  it("shows league admin link when persona=admin", () => {
    const sidebar = sidebarMarkup(renderAt("/leghe", "?persona=admin&stato=success"));
    expect(sidebar).toContain("Amministrazione lega");
    expect(sidebar).toContain('href="/lega/amministrazione"');
  });

  it("renders the collapsible Lega group in the sidebar", () => {
    const sidebar = sidebarMarkup(renderAt("/leghe", "?persona=admin&stato=success"));
    expect(sidebar).toContain('data-testid="sidebar-nav-group-league"');
    expect(sidebar).toContain('aria-expanded="true"');
    expect(sidebar).toContain("Le mie leghe");
    expect(sidebar).toContain('href="/lega/home"');
  });

  it("keeps Turni and Inviti outside the Lega group", () => {
    const sidebar = sidebarMarkup(renderAt("/leghe", "?persona=admin&stato=success"));
    const groupStart = sidebar.indexOf('class="fa-sidebar-nav__group-list"');
    expect(groupStart).toBeGreaterThan(-1);
    const insideGroup = sidebar.slice(groupStart, sidebar.indexOf("</ul>", groupStart));
    expect(insideGroup).not.toContain('href="/turni"');
    expect(insideGroup).not.toContain('href="/inviti"');
    expect(sidebar).toContain('href="/turni"');
    expect(sidebar).toContain('href="/inviti"');
  });

  it("blocks league admin route for members with forbidden state", () => {
    const html = renderAt("/lega/amministrazione", "?persona=member&stato=success");
    expect(html).toContain('data-testid="route-forbidden"');
    expect(html).toContain("Permessi insufficienti");
  });

  it("allows league admin route for admin persona", () => {
    const html = renderAt("/lega/amministrazione", "?persona=admin&stato=success");
    expect(html).toContain('data-testid="league-admin-form"');
    expect(html).not.toContain('data-testid="route-forbidden"');
  });

  it("blocks global admin route for members with forbidden state", () => {
    const html = renderAt("/admin", "?persona=member&stato=success");
    expect(html).toContain('data-testid="route-forbidden"');
    expect(html).not.toContain('data-testid="admin-dashboard-success"');
  });

  it("renders domain components on roster page", () => {
    const html = renderAt("/rosa");
    expect(html).toContain('data-testid="wireframe-roster-success"');
    expect(html).toContain('data-testid="roster-summary"');
  });

  it("renders formation view on formazione page", () => {
    const html = renderAt("/formazione");
    expect(html).toContain('data-testid="formation-view"');
  });

  it("renders leagues list or empty state on /leghe", () => {
    const html = renderAt("/leghe");
    expect(html).toContain('data-testid="leagues-create-link"');
  });

  it("uses keyboard-focusable nav links", () => {
    const html = renderAt("/mercato");
    expect(html).toContain('href="/mercato"');
    expect(html).toContain("Mercato");
  });

  it("includes classifica and formazione in member navigation", () => {
    const html = renderAt("/leghe");
    expect(html).toContain("Classifica");
    expect(html).toContain("Formazione");
    expect(html).toContain('href="/classifica"');
    expect(html).toContain('href="/formazione"');
    expect(html).toContain('data-testid="brand-logo"');
    expect(html).toContain('aria-label="FantApperò, home"');
  });

  it("includes asta in member navigation", () => {
    const html = renderAt("/leghe");
    expect(html).toContain("Asta");
    expect(html).toContain('href="/asta"');
  });

  it("renders standings page on /classifica", () => {
    const html = renderAt("/classifica");
    expect(html).toContain('data-testid="wireframe-standings-success"');
    expect(html).toContain('data-testid="standings-table"');
  });
});
