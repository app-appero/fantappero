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

  it("manda gli esiti degli svincolati alla pagina svincolati (QA 19-20/11)", () => {
    expect(
      resolveNotificationDestination({
        title: "Svincolato aggiudicato",
        deepLink: "/svincolati?lega=abc",
      }),
    ).toBe("/svincolati?lega=abc");
    for (const title of [
      "Svincolato aggiudicato",
      "Svincolato perso",
      "Spareggio svincolati aperto",
      "Spareggio svincolati annullato",
    ]) {
      expect(resolveNotificationDestination({ title, deepLink: null })).toBe("/svincolati");
    }
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