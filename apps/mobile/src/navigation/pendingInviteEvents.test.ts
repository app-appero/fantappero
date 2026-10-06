import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
  notifyPendingInvitesChanged,
  subscribePendingInvitesChanged,
} from "./pendingInviteEvents.ts";

describe("pendingInviteEvents", () => {
  it("notifies current subscribers and stops after unsubscribe", () => {
    const seen: number[] = [];
    const unsubscribe = subscribePendingInvitesChanged(() => {
      seen.push(1);
    });

    notifyPendingInvitesChanged();
    unsubscribe();
    notifyPendingInvitesChanged();

    assert.deepEqual(seen, [1]);
  });
});
