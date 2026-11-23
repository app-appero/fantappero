import { describe, expect, it } from "vitest";
import {
  notificationLeagueToActivate,
  resolveNotificationDestination,
  resolveNotificationExternalLink,
} from "./notificationDestination";

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

describe("notificationLeagueToActivate (Rosario 21/11)", () => {
  const session = { activeLeagueId: "lega-b", leagues: [{ id: "lega-a" }, { id: "lega-b" }] };

  it("la lega di ?lega= quando è un'altra lega dell'utente", () => {
    expect(notificationLeagueToActivate("/mercato?scambio=p-1&lega=lega-a", session)).toBe("lega-a");
    expect(notificationLeagueToActivate("/turni/scontro/slot-1?lega=lega-a", session)).toBe("lega-a");
    expect(notificationLeagueToActivate("/?lega=lega-a#home", session)).toBe("lega-a");
  });

  it("nessun cambio con la lega già attiva, senza ?lega= o con una lega non dell'utente", () => {
    expect(notificationLeagueToActivate("/formazione?lega=lega-b", session)).toBeNull();
    expect(notificationLeagueToActivate("/inviti", session)).toBeNull();
    expect(notificationLeagueToActivate("/classifica?lega=lega-lasciata", session)).toBeNull();
    expect(notificationLeagueToActivate("https://example.com/?lega=lega-a", session)).toBeNull();
  });
});
describe("resolveNotificationExternalLink (release 1.4)", () => {
  it("solo la notifica della nuova versione dell'app, e solo con un link https", () => {
    const title = "È disponibile la versione 1.4 dell'app";
    expect(resolveNotificationExternalLink({ title, deepLink: "https://drive.google.com/x" })).toBe(
      "https://drive.google.com/x",
    );
    expect(resolveNotificationExternalLink({ title, deepLink: "http://drive.google.com/x" })).toBeNull();
    expect(resolveNotificationExternalLink({ title, deepLink: "javascript:alert(1)" })).toBeNull();
    expect(resolveNotificationExternalLink({ title, deepLink: null })).toBeNull();
    expect(
      resolveNotificationExternalLink({ title: "Avviso", deepLink: "https://drive.google.com/x" }),
    ).toBeNull();
    // Il link esterno non è una pagina del sito.
    expect(resolveNotificationDestination({ title, deepLink: "https://drive.google.com/x" })).toBeNull();
  });
});
