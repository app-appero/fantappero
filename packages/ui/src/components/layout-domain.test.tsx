import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import {
  AnomalyIndicator,
  AppHeader,
  AppShell,
  BottomNav,
  Breadcrumb,
  FormationView,
  KpiCard,
  LeagueSelector,
  MatchCard,
  PageContainer,
  PlayerCard,
  ResultCard,
  SidebarNav,
} from "../index.js";

describe("EPUI-03 layout components", () => {
  it("renders app shell with sidebar and bottom nav landmarks", () => {
    const html = renderToStaticMarkup(
      createElement(
        AppShell,
        {
          surface: "app",
          header: createElement(AppHeader, { brand: "FantApperò" }),
          sidebar: createElement(SidebarNav, {
            items: [{ id: "a", label: "Turni", href: "/turni", active: true }],
          }),
          bottomNav: createElement(BottomNav, {
            items: [{ id: "a", label: "Turni", href: "/turni", active: true }],
          }),
        },
        createElement(PageContainer, { title: "Turni" }, "Contenuto"),
      ),
    );

    expect(html).toContain('data-testid="app-shell"');
    expect(html).toContain('data-testid="sidebar-nav"');
    expect(html).toContain('data-testid="bottom-nav"');
    expect(html).toContain('id="main-content"');
    expect(html).toContain('aria-current="page"');
  });

  it("applies admin visual treatment on global operator shell", () => {
    const html = renderToStaticMarkup(
      createElement(
        AppShell,
        { surface: "admin", header: createElement(AppHeader, { variant: "admin", brand: "Admin" }) },
        "Panel",
      ),
    );

    expect(html).toContain('data-surface="admin"');
    expect(html).toContain("fa-app-header--admin");
  });

  it("renders breadcrumb with current page marker", () => {
    const html = renderToStaticMarkup(
      createElement(Breadcrumb, {
        items: [
          { label: "Leghe", href: "/leghe" },
          { label: "Turni" },
        ],
      }),
    );

    expect(html).toContain('aria-current="page"');
    expect(html).toContain("Turni");
  });

  it("renders league selector with field label", () => {
    const html = renderToStaticMarkup(
      createElement(LeagueSelector, {
        label: "Lega attiva",
        leagues: [{ value: "l1", label: "Lega Demo" }],
        value: "l1",
        onChange: () => undefined,
      }),
    );

    expect(html).toContain('data-testid="league-selector"');
    expect(html).toContain("Lega attiva");
  });
});

describe("EPUI-03 domain components", () => {
  it("renders KPI, player, match, formation, result and anomaly blocks", () => {
    const html = renderToStaticMarkup(
      createElement(
        "div",
        null,
        createElement(KpiCard, { label: "Punti", value: 62, delta: "+4", trend: "up" }),
        createElement(PlayerCard, {
          name: "Rossi",
          role: "C",
          club: "Milan",
          rating: 6.5,
        }),
        createElement(MatchCard, {
          homeTeam: "A",
          awayTeam: "B",
          kickoffLabel: "Dom 15:00",
          status: "scheduled",
          statusLabel: "Programmata",
        }),
        createElement(FormationView, {
          title: "Modulo 4-3-3",
          slots: [{ id: "1", label: "P1", role: "P" }],
          pitchAriaLabel: "Titolari",
        }),
        createElement(ResultCard, {
          homeTeam: "Tu",
          awayTeam: "Avv",
          homeScore: 2,
          awayScore: 1,
          scoreAriaLabel: "Risultato",
        }),
        createElement(AnomalyIndicator, {
          severity: "warning",
          severityLabel: "Attenzione",
          message: "Voto provvisorio",
        }),
      ),
    );

    expect(html).toContain('data-testid="kpi-card"');
    expect(html).toContain('data-testid="player-card"');
    expect(html).toContain('data-testid="match-card"');
    expect(html).toContain('data-testid="formation-view"');
    expect(html).toContain("fa-badge--success");
    expect(html).toContain('data-testid="result-card"');
    expect(html).toContain('data-testid="anomaly-indicator"');
  });
});
