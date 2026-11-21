import assert from "node:assert/strict";
import { describe, it } from "node:test";
import type { NotificationItem } from "@fantappero/contracts";
import {
  allNotificationPagesLoaded,
  appendNotificationPage,
  notificationFilterCountLabel,
  NOTIFICATIONS_PAGE_SIZE,
} from "./notificationPages.ts";

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

describe("allNotificationPagesLoaded", () => {
  it("falso finché restano pagine, vero all'ultima o senza notifiche", () => {
    assert.equal(allNotificationPagesLoaded(1, 3), false);
    assert.equal(allNotificationPagesLoaded(3, 3), true);
    assert.equal(allNotificationPagesLoaded(1, 0), true);
  });
});

describe("notificationFilterCountLabel (QA 20-21/11: i filtri contavano solo le notifiche caricate)", () => {
  it("«Tutte» mostra il totale dell'API, non le 30 caricate finora", () => {
    assert.equal(notificationFilterCountLabel({ loaded: 30, total: 75, allLoaded: false }), "75");
    assert.equal(notificationFilterCountLabel({ loaded: 75, total: 75, allLoaded: true }), "75");
  });

  it("«Tutte» non scende sotto quelle in elenco e senza notifiche non ha numero", () => {
    // Una notifica già in elenco tolta dal server (es. invito annullato) prima dell'ultima
    // pagina letta: l'elenco ne ha una in più del totale.
    assert.equal(notificationFilterCountLabel({ loaded: 31, total: 30, allLoaded: true }), "31");
    assert.equal(notificationFilterCountLabel({ loaded: 0, total: 0, allLoaded: true }), "");
  });

  it("un gruppo è un minimo («12+») finché restano pagine da caricare", () => {
    assert.equal(notificationFilterCountLabel({ loaded: 12, allLoaded: false }), "12+");
    assert.equal(notificationFilterCountLabel({ loaded: 12, total: null, allLoaded: false }), "12+");
  });

  it("un gruppo è esatto quando è caricato tutto", () => {
    assert.equal(notificationFilterCountLabel({ loaded: 12, allLoaded: true }), "12");
  });

  it("un gruppo vuoto non ha numero", () => {
    assert.equal(notificationFilterCountLabel({ loaded: 0, allLoaded: false }), "");
    assert.equal(notificationFilterCountLabel({ loaded: 0, allLoaded: true }), "");
  });
});
