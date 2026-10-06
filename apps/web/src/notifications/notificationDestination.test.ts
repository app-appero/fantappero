import { describe, expect, it } from "vitest";
import { resolveNotificationDestination } from "./notificationDestination";

describe("resolveNotificationDestination", () => {
  it("manda l'invito di lega agli inviti ricevuti", () => {
    expect(
      resolveNotificationDestination({
        title: "Nuovo invito a una lega",
        deepLink: "/inviti",
      }),
    ).toBe("/inviti");
  });

  it("usa il titolo se il deep link manca", () => {
    expect(
      resolveNotificationDestination({
        title: "Nuovo invito a una lega",
        deepLink: null,
      }),
    ).toBe("/inviti");
  });

  it("ignora un link esterno", () => {
    expect(
      resolveNotificationDestination({
        title: "Avviso",
        deepLink: "https://example.com/inviti",
      }),
    ).toBeNull();
  });
});