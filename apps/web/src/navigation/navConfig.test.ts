import { describe, expect, it } from "vitest";
import { hasPermissions, type PermissionContext } from "@fantappero/contracts";
import {
  ADMIN_NAV_ITEMS,
  APP_NAV_GROUPS,
  APP_NAV_ITEMS,
  NAV_LABELS,
  filterNavItems,
} from "./navConfig";

const memberContext: PermissionContext = {
  user: { id: "u1", displayName: "M", globalRole: "member" },
  activeLeague: { id: "l1", name: "L", role: "member" },
};

const adminContext: PermissionContext = {
  user: { id: "u1", displayName: "M", globalRole: "member" },
  activeLeague: { id: "l1", name: "L", role: "league_admin" },
};

const operatorContext: PermissionContext = {
  user: { id: "op", displayName: "O", globalRole: "global_operator" },
  activeLeague: null,
};

function canFactory(context: PermissionContext) {
  return (required: Parameters<typeof hasPermissions>[1]) =>
    hasPermissions(context, required);
}

describe("filterNavItems", () => {
  it("shows the compact league and market hubs to regular members", () => {
    const items = filterNavItems(APP_NAV_ITEMS, canFactory(memberContext), "/turni");
    const ids = items.map((item) => item.id);
    expect(ids).toContain("league-hub");
    expect(ids).toContain("market-hub");
    expect(ids).toContain("matchday");
  });

  it("marks active route", () => {
    const items = filterNavItems(APP_NAV_ITEMS, canFactory(memberContext), "/mercato");
    const marketHub = items.find((item) => item.id === "market-hub");
    expect(marketHub?.active).toBe(true);
  });

  it("keeps ai-controlled managers on the same member catalog", () => {
    // Un fantallenatore IA è un membro di lega: stesse voci, nessuna amministrazione.
    const aiContext: PermissionContext = {
      user: { id: "ai-1", displayName: "IA", globalRole: "member" },
      activeLeague: { id: "l1", name: "L", role: "member" },
    };
    const ids = filterNavItems(APP_NAV_ITEMS, canFactory(aiContext), "/turni").map(
      (item) => item.id,
    );
    expect(ids).toContain("league-hub");
    expect(ids).toContain("market-hub");
  });

  it("shows the same league-hub entry to league administrators", () => {
    const items = filterNavItems(APP_NAV_ITEMS, canFactory(adminContext), "/leghe");
    expect(items.map((item) => item.id)).toContain("league-hub");
  });

  it("exposes admin surface only to global operator permissions", () => {
    const memberItems = filterNavItems(ADMIN_NAV_ITEMS, canFactory(memberContext), "/admin");
    const operatorItems = filterNavItems(
      ADMIN_NAV_ITEMS,
      canFactory(operatorContext),
      "/admin",
    );
    expect(memberItems).toHaveLength(0);
    expect(operatorItems.length).toBeGreaterThan(0);
  });
});

describe("hub a tab: Lega e Movimento giocatori (EP13-P01)", () => {
  it("non usa più gruppi collassabili nella sidebar: le destinazioni correlate sono tab in pagina", () => {
    expect(APP_NAV_GROUPS).toEqual([]);
  });

  it("usa le etichette compatte richieste dalla card", () => {
    expect(NAV_LABELS["league-hub"]).toBe("Lega");
    expect(NAV_LABELS["market-hub"]).toBe("Mercato");
  });

  it("punta ai path canonici degli hub", () => {
    const byId = new Map(APP_NAV_ITEMS.map((item) => [item.id, item.path]));
    expect(byId.get("league-hub")).toBe("/leghe");
    expect(byId.get("market-hub")).toBe("/mercato");
  });
});
