import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { hasPermissions, type PermissionContext } from "../../../../packages/contracts/src/auth.ts";
import { MOBILE_NAV_ITEMS } from "./navConfig.ts";

const memberContext: PermissionContext = {
  user: { id: "u1", displayName: "M", globalRole: "member" },
  activeLeague: { id: "l1", name: "L", role: "member" },
};

describe("mobile navigation", () => {
  it("shows standard tabs for demo member", () => {
    const visible = MOBILE_NAV_ITEMS.filter((item) =>
      hasPermissions(memberContext, item.requiredPermissions),
    );
    assert.ok(visible.length >= 4);
    assert.ok(visible.some((item) => item.id === "roster"));
    assert.ok(!visible.some((item) => item.id === "league-admin"));
  });
});
