import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { hasPermissions, type PermissionContext } from "../../../../packages/contracts/src/auth.ts";
import {
  MOBILE_ADMIN_NAV_ITEMS,
  MOBILE_DRAWER_NAV_ITEMS,
  MOBILE_NAV_GROUPS,
  NAV_LABELS,
  buildMobileNavSections,
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
    assert.ok(visible.some((item) => item.id === "league-hub"));
    assert.ok(visible.some((item) => item.id === "received-invites"));
    assert.ok(visible.some((item) => item.id === "standings"));
    assert.ok(visible.some((item) => item.id === "formation"));
    assert.ok(visible.some((item) => item.id === "market-hub"));
    assert.ok(visible.some((item) => item.id === "profile"));
    assert.ok(!visible.some((item) => item.id === "manager-directory"));
  });

  it("shows the same league-hub entry and the directory only to league admins", () => {
    const visible = filterMobileNavItems(
      MOBILE_DRAWER_NAV_ITEMS,
      (required) => hasPermissions(adminContext, required),
    );
    assert.ok(visible.some((item) => item.id === "league-hub"));
    assert.ok(visible.some((item) => item.id === "manager-directory"));
  });

  it("exposes admin routes only to global operator", () => {
    const operatorVisible = filterMobileNavItems(
      MOBILE_ADMIN_NAV_ITEMS,
      (required) => hasPermissions(operatorContext, required),
    );
    assert.equal(operatorVisible.length, 5);
    const memberVisible = filterMobileNavItems(
      MOBILE_ADMIN_NAV_ITEMS,
      (required) => hasPermissions(memberContext, required),
    );
    assert.equal(memberVisible.length, 0);
  });
});

describe("hub a tab: Lega e Mercato — mobile (EP13-P01)", () => {
  it("non usa più gruppi collassabili nel drawer: le destinazioni correlate sono screen-tabs", () => {
    assert.deepEqual(MOBILE_NAV_GROUPS, []);
    const sections = buildMobileNavSections(
      filterMobileNavItems(MOBILE_DRAWER_NAV_ITEMS, (required) =>
        hasPermissions(adminContext, required),
      ),
    );
    assert.ok(!sections.some((section) => section.kind === "group"));
  });

  it("usa le etichette compatte richieste dalla card", () => {
    assert.equal(NAV_LABELS["league-hub"], "Lega");
    assert.equal(NAV_LABELS["market-hub"], "Mercato");
  });

  it("punta ai path canonici degli hub", () => {
    const byId = new Map(MOBILE_DRAWER_NAV_ITEMS.map((item) => [item.id, item.path]));
    assert.equal(byId.get("league-hub"), "/leghe");
    assert.equal(byId.get("market-hub"), "/mercato");
  });
});
