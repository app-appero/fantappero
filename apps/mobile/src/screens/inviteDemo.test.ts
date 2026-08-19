import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
  resolveAdminInviteState,
  resolveAdminMemberState,
  resolveJoinInviteState,
  resolveLeagueCalendarState,
  resolveLeagueSeasonState,
} from "./inviteDemo.ts";

describe("EP03-03 mobile invitation states", () => {
  it("covers admin positive, empty, loading and error states", () => {
    assert.equal(resolveAdminInviteState(true), "success");
    assert.equal(resolveAdminInviteState(true, "empty"), "empty");
    assert.equal(resolveAdminInviteState(true, "loading"), "loading");
    assert.equal(resolveAdminInviteState(true, "error"), "error");
  });

  it("blocks invitation management without league admin permission", () => {
    assert.equal(resolveAdminInviteState(false, "success"), "forbidden");
  });

  it("covers participant states and insufficient permissions", () => {
    assert.equal(resolveAdminMemberState(true), "success");
    assert.equal(resolveAdminMemberState(true, "empty"), "empty");
    assert.equal(resolveAdminMemberState(true, "loading"), "loading");
    assert.equal(resolveAdminMemberState(true, "error"), "error");
    assert.equal(resolveAdminMemberState(false), "forbidden");
  });

  it("covers season lifecycle UI states and permissions", () => {
    assert.equal(resolveLeagueSeasonState(true), "success");
    assert.equal(resolveLeagueSeasonState(true, "empty"), "empty");
    assert.equal(resolveLeagueSeasonState(true, "loading"), "loading");
    assert.equal(resolveLeagueSeasonState(true, "error"), "error");
    assert.equal(resolveLeagueSeasonState(false), "forbidden");
  });

  it("covers calendar UI states and permissions", () => {
    assert.equal(resolveLeagueCalendarState(true), "success");
    assert.equal(resolveLeagueCalendarState(true, "empty"), "empty");
    assert.equal(resolveLeagueCalendarState(true, "loading"), "loading");
    assert.equal(resolveLeagueCalendarState(true, "error"), "error");
    assert.equal(resolveLeagueCalendarState(false), "forbidden");
  });

  it("covers join empty, success, loading, error and forbidden states", () => {
    assert.equal(resolveJoinInviteState(true), "empty");
    assert.equal(resolveJoinInviteState(true, "success"), "success");
    assert.equal(resolveJoinInviteState(true, "loading"), "loading");
    assert.equal(resolveJoinInviteState(true, "error"), "error");
    assert.equal(resolveJoinInviteState(false), "forbidden");
  });
});
