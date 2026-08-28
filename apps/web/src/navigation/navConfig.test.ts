import { describe, expect, it } from "vitest";
import { hasPermissions, type PermissionContext } from "@fantappero/contracts";
import {
  ADMIN_NAV_ITEMS,
  APP_NAV_GROUPS,
  APP_NAV_ITEMS,
  NAV_LABELS,
  filterNavItems,
  resolveNavGroups,
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
  it("hides league admin nav for regular members", () => {
    const items = filterNavItems(APP_NAV_ITEMS, canFactory(memberContext), "/turni");
    const ids = items.map((item) => item.id);
    expect(ids).not.toContain("league-admin");
    expect(ids).toContain("matchday");
    expect(ids).toContain("league-home");
  });

  it("shows league admin nav for league administrators", () => {
    const items = filterNavItems(APP_NAV_ITEMS, canFactory(adminContext), "/turni");
    expect(items.map((item) => item.id)).toContain("league-admin");
  });

  it("marks active route", () => {
    const items = filterNavItems(APP_NAV_ITEMS, canFactory(memberContext), "/rosa");
    const roster = items.find((item) => item.id === "roster");
    expect(roster?.active).toBe(true);
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
    expect(ids).toContain("leagues");
    expect(ids).toContain("league-home");
    expect(ids).not.toContain("league-admin");
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

describe("gruppo di navigazione Lega (EP13-P01)", () => {
  it("raccoglie le tre destinazioni di lega e lascia fuori Turni e Inviti", () => {
    const group = APP_NAV_GROUPS.find((candidate) => candidate.id === "league");
    expect(group?.itemIds).toEqual(["leagues", "league-home", "league-admin"]);
    expect(group?.itemIds).not.toContain("matchday");
    expect(group?.itemIds).not.toContain("received-invites");
  });

  it("referenzia solo voci esistenti nel catalogo", () => {
    const knownIds = new Set(APP_NAV_ITEMS.map((item) => item.id));
    for (const group of APP_NAV_GROUPS) {
      for (const itemId of group.itemIds) {
        expect(knownIds.has(itemId)).toBe(true);
      }
    }
  });

  it("risolve la label del gruppo", () => {
    expect(resolveNavGroups()).toEqual([
      { id: "league", label: "Lega", itemIds: ["leagues", "league-home", "league-admin"] },
    ]);
  });

  it("usa le etichette esplicite richieste dalla card", () => {
    expect(NAV_LABELS.leagues).toBe("Le mie leghe");
    expect(NAV_LABELS["league-home"]).toBe("Home lega");
    expect(NAV_LABELS["league-admin"]).toBe("Amministrazione lega");
  });

  it("non altera i path delle destinazioni raggruppate", () => {
    const byId = new Map(APP_NAV_ITEMS.map((item) => [item.id, item.path]));
    expect(byId.get("leagues")).toBe("/leghe");
    expect(byId.get("league-home")).toBe("/lega/home");
    expect(byId.get("league-admin")).toBe("/lega/amministrazione");
  });
});
