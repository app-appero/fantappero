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
    assert.equal(operatorVisible.length, 5);
    const memberVisible = filterMobileNavItems(
      MOBILE_ADMIN_NAV_ITEMS,
      (required) => hasPermissions(memberContext, required),
    );
    assert.equal(memberVisible.length, 0);
  });
});

describe("gruppo di navigazione Lega — mobile (EP13-P01)", () => {
  function sectionsFor(context: PermissionContext) {
    return buildMobileNavSections(
      filterMobileNavItems(MOBILE_DRAWER_NAV_ITEMS, (required) =>
        hasPermissions(context, required),
      ),
    );
  }

  it("usa lo stesso gruppo e le stesse etichette del web", () => {
    assert.deepEqual(MOBILE_NAV_GROUPS.map((group) => group.id), ["league"]);
    assert.deepEqual(MOBILE_NAV_GROUPS[0].itemIds, [
      "leagues",
      "league-home",
      "league-admin",
    ]);
    assert.equal(NAV_LABELS.leagues, "Le mie leghe");
    assert.equal(NAV_LABELS["league-home"], "Home lega");
    assert.equal(NAV_LABELS["league-admin"], "Amministrazione lega");
  });

  it("mostra all'admin di lega le tre voci dentro il gruppo", () => {
    const group = sectionsFor(adminContext).find(
      (section) => section.kind === "group" && section.id === "league",
    );
    assert.ok(group && group.kind === "group");
    assert.deepEqual(group.items.map((item) => item.id), [
      "leagues",
      "league-home",
      "league-admin",
    ]);
    assert.equal(group.label, "Lega");
  });

  it("nasconde al membro la voce di amministrazione dentro il gruppo", () => {
    const group = sectionsFor(memberContext).find(
      (section) => section.kind === "group" && section.id === "league",
    );
    assert.ok(group && group.kind === "group");
    assert.deepEqual(group.items.map((item) => item.id), ["leagues", "league-home"]);
  });

  it("tiene Turni e Inviti fuori dal gruppo", () => {
    const standalone = sectionsFor(memberContext)
      .filter((section) => section.kind === "item")
      .map((section) => (section.kind === "item" ? section.item.id : ""));
    assert.ok(standalone.includes("matchday"));
    assert.ok(standalone.includes("received-invites"));
  });

  it("non altera i path delle destinazioni raggruppate", () => {
    const byId = new Map(MOBILE_DRAWER_NAV_ITEMS.map((item) => [item.id, item.path]));
    assert.equal(byId.get("leagues"), "/leghe");
    assert.equal(byId.get("league-home"), "/lega/home");
    assert.equal(byId.get("league-admin"), "/lega/amministrazione");
  });

  it("omette il gruppo quando nessuna voce di lega è autorizzata", () => {
    const sections = buildMobileNavSections(
      filterMobileNavItems(MOBILE_DRAWER_NAV_ITEMS, (required) =>
        hasPermissions(memberContext, required),
      ).filter((item) => !MOBILE_NAV_GROUPS[0].itemIds.includes(item.id)),
    );
    assert.ok(!sections.some((section) => section.kind === "group"));
  });
});
