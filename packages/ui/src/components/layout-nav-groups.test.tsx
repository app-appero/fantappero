import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { SidebarNav } from "../index.js";
import type { NavGroupItem, NavLinkItem } from "../index.js";

const ITEMS: NavLinkItem[] = [
  { id: "leagues", label: "Le mie leghe", href: "/leghe" },
  { id: "league-home", label: "Home lega", href: "/lega/home" },
  { id: "matchday", label: "Turni", href: "/turni", active: true },
  { id: "received-invites", label: "Inviti", href: "/inviti" },
  { id: "league-admin", label: "Amministrazione lega", href: "/lega/amministrazione" },
];

const GROUPS: NavGroupItem[] = [
  { id: "league", label: "Lega", itemIds: ["leagues", "league-home", "league-admin"] },
];

function render(props: Parameters<typeof SidebarNav>[0]) {
  return renderToStaticMarkup(createElement(SidebarNav, props));
}

/** Estrae il markup del sottomenu del gruppo (EP13-P01). */
function groupListMarkup(html: string): string {
  const start = html.indexOf('class="fa-sidebar-nav__group-list"');
  expect(start).toBeGreaterThan(-1);
  const end = html.indexOf("</ul>", start);
  return html.slice(start, end);
}

describe("SidebarNav — gruppo Lega (EP13-P01)", () => {
  it("mantiene la lista piatta quando non riceve gruppi", () => {
    const html = render({ items: ITEMS });
    expect(html).not.toContain("fa-sidebar-nav__group");
    expect(html).toContain('href="/leghe"');
    expect(html).toContain('href="/lega/amministrazione"');
  });

  it("raccoglie nel gruppo solo le tre destinazioni di lega", () => {
    const html = render({ items: ITEMS, groups: GROUPS });
    const inner = groupListMarkup(html);

    expect(inner).toContain('href="/leghe"');
    expect(inner).toContain('href="/lega/home"');
    expect(inner).toContain('href="/lega/amministrazione"');
    // Turni e Inviti restano destinazioni indipendenti.
    expect(inner).not.toContain('href="/turni"');
    expect(inner).not.toContain('href="/inviti"');
    expect(html).toContain('href="/turni"');
    expect(html).toContain('href="/inviti"');
  });

  it("espone il gruppo come toggle accessibile aperto per default", () => {
    const html = render({ items: ITEMS, groups: GROUPS });
    expect(html).toContain('data-testid="sidebar-nav-group-league"');
    expect(html).toContain('aria-expanded="true"');
    expect(html).toContain("aria-controls=");
    expect(html).toContain("Lega");
  });

  it("nasconde il sottomenu quando il gruppo è chiuso", () => {
    const html = render({ items: ITEMS, groups: GROUPS, expandedGroupIds: [] });
    expect(html).toContain('aria-expanded="false"');
    expect(html).toContain("hidden");
    // Le voci restano nel DOM (e raggiungibili via URL), solo non visibili.
    expect(groupListMarkup(html)).toContain('href="/lega/home"');
  });

  it("evidenzia il gruppo che contiene la voce attiva", () => {
    const activeInsideGroup = ITEMS.map((item) => ({
      ...item,
      active: item.id === "league-home",
    }));
    const html = render({ items: activeInsideGroup, groups: GROUPS });
    expect(html).toContain("fa-sidebar-nav__group-toggle--active");
  });

  it("non evidenzia il gruppo quando la voce attiva è esterna", () => {
    const html = render({ items: ITEMS, groups: GROUPS });
    expect(html).not.toContain("fa-sidebar-nav__group-toggle--active");
  });

  it("omette il gruppo quando nessuna sua voce è autorizzata", () => {
    const onlyOutside = ITEMS.filter((item) => !GROUPS[0].itemIds.includes(item.id));
    const html = render({ items: onlyOutside, groups: GROUPS });
    expect(html).not.toContain('data-testid="sidebar-nav-group-league"');
    expect(html).toContain('href="/turni"');
  });

  it("rende il gruppo anche con una sola voce autorizzata", () => {
    const memberItems = ITEMS.filter((item) => item.id !== "league-admin");
    const html = render({ items: memberItems, groups: GROUPS });
    const inner = groupListMarkup(html);
    expect(inner).toContain('href="/leghe"');
    expect(inner).not.toContain('href="/lega/amministrazione"');
  });
});

describe("SidebarNav — badge inviti pendenti (EP13-P07)", () => {
  const withBadge = (count: number): NavLinkItem[] => [
    { id: "matchday", label: "Turni", href: "/turni" },
    {
      id: "received-invites",
      label: "Inviti ricevuti",
      href: "/inviti",
      badgeCount: count,
      badgeLabel: `${count} inviti in attesa di risposta`,
    },
  ];

  it("mostra il conteggio quando ci sono inviti pendenti", () => {
    const html = render({ items: withBadge(3) });
    expect(html).toContain('data-testid="sidebar-nav-badge-received-invites"');
    expect(html).toContain(">3<");
    expect(html).toContain("3 inviti in attesa di risposta");
  });

  it("nasconde il badge quando il conteggio è zero", () => {
    const html = render({ items: withBadge(0) });
    expect(html).not.toContain('data-testid="sidebar-nav-badge-received-invites"');
    expect(html).toContain('href="/inviti"');
  });

  it("comprime i conteggi oltre 99", () => {
    expect(render({ items: withBadge(150) })).toContain(">99+<");
    expect(render({ items: withBadge(99) })).toContain(">99<");
  });

  it("non mette il badge sulle altre voci", () => {
    const html = render({ items: withBadge(5) });
    expect(html).not.toContain('data-testid="sidebar-nav-badge-matchday"');
  });
});
