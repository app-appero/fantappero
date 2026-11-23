import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { describe, it } from "node:test";
import {
  PROFILE_NOTIFICATIONS_TAB_A11Y_LABEL,
  PROFILE_TABS,
  notificationsBellLabel,
} from "./notificationLabels.ts";

const read = (path: string) => readFileSync(new URL(path, import.meta.url), "utf8");

describe("«Notifiche» del Profilo e campanello con nomi diversi (corsa M4, 22/11)", () => {
  it("il campanello resta «Notifiche», con il numero delle non lette", () => {
    assert.equal(notificationsBellLabel(0), "Notifiche");
    assert.equal(notificationsBellLabel(3), "Notifiche: 3 non lette");
  });

  it("la scheda del Profilo ha un nome diverso dal campanello, con dentro il testo visibile", () => {
    const tab = PROFILE_TABS.find((item) => item.id === "notifiche");
    assert.ok(tab && "accessibilityLabel" in tab);
    assert.equal(tab.label, "Notifiche");
    assert.equal(tab.accessibilityLabel, PROFILE_NOTIFICATIONS_TAB_A11Y_LABEL);
    for (const unread of [0, 1, 9, 12]) {
      assert.notEqual(tab.accessibilityLabel, notificationsBellLabel(unread));
    }
    // Il nome contiene il testo che si vede (WCAG 2.5.3, «Label in Name»).
    assert.match(tab.accessibilityLabel.toLocaleLowerCase("it-IT"), /notifiche/);
  });

  it("l'id dei flussi Maestro resta profile-tabs-notifiche", () => {
    assert.deepEqual(
      PROFILE_TABS.map((item) => item.id),
      ["utente", "notifiche"],
    );
    const profile = read("../screens/ProfileScreen.tsx");
    assert.match(profile, /items=\{PROFILE_TABS\}/);
    assert.match(profile, /testID="profile-tabs"/);
    const tabs = read("../components/ScreenTabs.tsx");
    assert.match(tabs, /testID=\{`\$\{testID\}-\$\{item\.id\}`\}/);
    assert.match(tabs, /accessibilityLabel=\{item\.accessibilityLabel\}/);
    assert.match(read("./AppHeader.tsx"), /accessibilityLabel=\{notificationsBellLabel\(unreadNotifications\)\}/);
  });
});
