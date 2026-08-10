import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { hasPermissions, type PermissionContext } from "../../../../packages/contracts/src/auth.ts";
import {
  MOBILE_ADMIN_NAV_ITEMS,
  MOBILE_DRAWER_NAV_ITEMS,
  filterMobileNavItems,
} from "./navConfig.ts";

const memberContext: PermissionContext = {
  user: { id: "u1", displayName: "M", globalRole: "member" },
  activeLeague: { id: "l1", name: "L", role: "member" },
};

const adminContext: PermissionContext = {
  user: { id: "u2", displayName: "A", globalRole: "member" },
  activeLeague: { id: "l2", name: "LA", role: "league_admin" },
};

const operatorContext: PermissionContext = {
  user: { id: "u3", displayName: "O", globalRole: "global_operator" },
  activeLeague: null,
};

describe("mobile navigation", () => {
  it("aligns drawer catalog with web member routes", () => {
    const visible = filterMobileNavItems(
      MOBILE_DRAWER_NAV_ITEMS,
      (required) => hasPermissions(memberContext, required),
    );
    assert.ok(visible.some((item) => item.id === "leagues"));
    assert.ok(visible.some((item) => item.id === "league-home"));
    assert.ok(visible.some((item) => item.id === "received-invites"));
    assert.ok(visible.some((item) => item.id === "standings"));
    assert.ok(visible.some((item) => item.id === "formation"));
    assert.ok(visible.some((item) => item.id === "auction"));
    assert.ok(visible.some((item) => item.id === "profile"));
    assert.ok(!visible.some((item) => item.id === "league-admin"));
    assert.ok(!visible.some((item) => item.id === "manager-directory"));
  });

  it("shows league admin and directory only to league admins", () => {
    const visible = filterMobileNavItems(
      MOBILE_DRAWER_NAV_ITEMS,
      (required) => hasPermissions(adminContext, required),
    );
    assert.ok(visible.some((item) => item.id === "league-admin"));
    assert.ok(visible.some((item) => item.id === "manager-directory"));
  });

  it("exposes admin routes only to global operator", () => {
    const operatorVisible = filterMobileNavItems(
      MOBILE_ADMIN_NAV_ITEMS,
      (required) => hasPermissions(operatorContext, required),
    );
    assert.equal(operatorVisible.length, 3);
    const memberVisible = filterMobileNavItems(
      MOBILE_ADMIN_NAV_ITEMS,
      (required) => hasPermissions(memberContext, required),
    );
    assert.equal(memberVisible.length, 0);
  });
});
