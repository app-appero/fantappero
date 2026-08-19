import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
  hasPermissions,
  resolvePermissions,
  type PermissionContext,
} from "./auth.ts";

const memberUser = {
  id: "u1",
  displayName: "Marco",
  globalRole: "member" as const,
};

const operatorUser = {
  id: "op1",
  displayName: "Operatore",
  globalRole: "global_operator" as const,
};

const leagueMember: PermissionContext = {
  user: memberUser,
  activeLeague: { id: "l1", name: "Lega Demo", role: "member" },
};

const leagueAdmin: PermissionContext = {
  user: memberUser,
  activeLeague: { id: "l1", name: "Lega Demo", role: "league_admin" },
};

const globalOperator: PermissionContext = {
  user: operatorUser,
  activeLeague: null,
};

describe("resolvePermissions", () => {
  it("grants market:manage to league admin but not to member", () => {
    const adminPerms = resolvePermissions(leagueAdmin);
    const memberPerms = resolvePermissions(leagueMember);

    assert.equal(adminPerms.has("market:manage"), true);
    assert.equal(memberPerms.has("market:manage"), false);
  });

  it("grants global:operate only to global operator", () => {
    assert.equal(resolvePermissions(globalOperator).has("global:operate"), true);
    assert.equal(resolvePermissions(leagueMember).has("global:operate"), false);
    assert.equal(resolvePermissions(leagueAdmin).has("global:operate"), false);
  });

  it("always includes profile:view for authenticated league contexts", () => {
    assert.equal(resolvePermissions(leagueMember).has("profile:view"), true);
  });
});

describe("hasPermissions", () => {
  it("returns false when any required permission is missing", () => {
    assert.equal(
      hasPermissions(leagueMember, ["market:view", "market:manage"]),
      false,
    );
    assert.equal(
      hasPermissions(leagueAdmin, ["market:view", "market:manage"]),
      true,
    );
  });

  it("returns true for empty requirement list", () => {
    assert.equal(hasPermissions(leagueMember, []), true);
  });
});
