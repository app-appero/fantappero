import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
  DEMO_COACHES,
  resolveDirectoryState,
  resolveNominalInviteOutcome,
  resolveReceivedInvitesState,
} from "./directoryDemo.ts";

describe("directory fantallenatori demo", () => {
  it("covers standard directory UI states and permission precedence", () => {
    assert.equal(resolveDirectoryState(true), "success");
    assert.equal(resolveDirectoryState(true, "loading"), "loading");
    assert.equal(resolveDirectoryState(true, "empty"), "empty");
    assert.equal(resolveDirectoryState(true, "error"), "error");
    assert.equal(resolveDirectoryState(false, "success"), "forbidden");
  });

  it("resolves unavailable, already invited, capacity and success outcomes", () => {
    const available = DEMO_COACHES.find((coach) => coach.id === "coach-giulia");
    const invited = DEMO_COACHES.find((coach) => coach.id === "coach-luca");
    const unavailable = DEMO_COACHES.find((coach) => coach.id === "coach-sara");
    const ai = DEMO_COACHES.find((coach) => coach.id === "coach-ai");
    assert.ok(available);
    assert.ok(invited);
    assert.ok(unavailable);
    assert.ok(ai);

    assert.equal(available.userType, "human");
    assert.equal(ai.userType, "ai");
    assert.equal(resolveNominalInviteOutcome(available, 2, 8), "success");
    assert.equal(resolveNominalInviteOutcome(unavailable, 2, 8), "unavailable");
    assert.equal(resolveNominalInviteOutcome(invited, 2, 8), "already-invited");
    assert.equal(resolveNominalInviteOutcome(available, 8, 8), "capacity");
    assert.equal(resolveNominalInviteOutcome(ai, 2, 8), "success");
  });

  it("covers received invite states", () => {
    assert.equal(resolveReceivedInvitesState(true), "success");
    assert.equal(resolveReceivedInvitesState(true, "loading"), "loading");
    assert.equal(resolveReceivedInvitesState(true, "empty"), "empty");
    assert.equal(resolveReceivedInvitesState(true, "error"), "error");
    assert.equal(resolveReceivedInvitesState(true, "unavailable"), "unavailable");
    assert.equal(resolveReceivedInvitesState(true, "already-invited"), "already-invited");
    assert.equal(resolveReceivedInvitesState(true, "capacity"), "capacity");
    assert.equal(resolveReceivedInvitesState(false), "forbidden");
  });
});
