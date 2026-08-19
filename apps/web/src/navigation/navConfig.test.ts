import { describe, expect, it } from "vitest";
import { hasPermissions, type PermissionContext } from "@fantappero/contracts";
import { ADMIN_NAV_ITEMS, APP_NAV_ITEMS, filterNavItems } from "./navConfig";

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
