import assert from "node:assert/strict";
import { describe, it } from "node:test";
import type { NotificationItem } from "@fantappero/contracts";
import { appendNotificationPage, NOTIFICATIONS_PAGE_SIZE } from "./notificationPages.ts";

function item(id: string): NotificationItem {
  return { id } as NotificationItem;
}

describe("appendNotificationPage", () => {
  it("appends older notifications after the loaded ones", () => {
    assert.deepEqual(
      appendNotificationPage([item("a"), item("b")], [item("c"), item("d")]).map((row) => row.id),
      ["a", "b", "c", "d"],
    );
  });

  it("skips notifications already loaded (a new one shifted the pages)", () => {
    assert.deepEqual(
      appendNotificationPage([item("a"), item("b")], [item("b"), item("c")]).map((row) => row.id),
      ["a", "b", "c"],
    );
  });

  it("keeps the page size used by the screen", () => {
    assert.equal(NOTIFICATIONS_PAGE_SIZE, 30);
  });
});
