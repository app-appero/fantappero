import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { hasPermissions, type PermissionContext } from "../../../../packages/contracts/src/auth.ts";
import {
  MOBILE_ADMIN_NAV_ITEMS,
  MOBILE_LEAGUE_ADMIN_ITEM,
  MOBILE_NAV_ITEMS,
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
  it("shows all member tabs aligned with web for demo member", () => {
    const visible = filterMobileNavItems(
      MOBILE_NAV_ITEMS,
      (required) => hasPermissions(memberContext, required),
    );
    assert.equal(visible.length, 8);
    assert.ok(visible.some((item) => item.id === "leagues"));
    assert.ok(visible.some((item) => item.id === "standings"));
    assert.ok(visible.some((item) => item.id === "formation"));
    assert.ok(visible.some((item) => item.id === "auction"));
    assert.ok(!visible.some((item) => item.id === "league-admin"));
  });

  it("keeps league admin outside tab bar", () => {
    assert.ok(!MOBILE_NAV_ITEMS.some((item) => item.id === "league-admin"));
    assert.equal(MOBILE_LEAGUE_ADMIN_ITEM.id, "league-admin");
    assert.ok(hasPermissions(adminContext, MOBILE_LEAGUE_ADMIN_ITEM.requiredPermissions));
    assert.ok(!hasPermissions(memberContext, MOBILE_LEAGUE_ADMIN_ITEM.requiredPermissions));
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
