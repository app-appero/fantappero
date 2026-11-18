import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
  APP_LINK_PREFIXES,
  planAppLink,
  routeForAppLinkPath,
  routeForAppLinkUrl,
} from "./deepLinks.ts";

describe("routeForAppLinkPath", () => {
  it("maps the links sent by email to the app screens", () => {
    assert.deepEqual(routeForAppLinkPath("accedi/verifica?token=abc"), {
      name: "AuthVerifyEmail",
      params: { token: "abc" },
    });
    assert.deepEqual(routeForAppLinkPath("/accedi/reimposta-password?token=r1"), {
      name: "AuthResetPassword",
      params: { token: "r1" },
    });
    assert.deepEqual(routeForAppLinkPath("leghe/invito/?token=t%2B1"), {
      name: "JoinLeague",
      params: { token: "t+1" },
    });
  });

  it("ignores links without a token and unknown paths", () => {
    assert.equal(routeForAppLinkPath("accedi/verifica"), null);
    assert.equal(routeForAppLinkPath("accedi/verifica?token=%20"), null);
    assert.equal(routeForAppLinkPath("mercato?token=x"), null);
  });
});

describe("routeForAppLinkUrl", () => {
  it("accepts every environment, production included, and the app scheme", () => {
    for (const host of ["dev.fantappero.it", "pilota.fantappero.it", "fantappero.it", "www.fantappero.it"]) {
      assert.deepEqual(routeForAppLinkUrl(`https://${host}/leghe/invito?token=i`), {
        name: "JoinLeague",
        params: { token: "i" },
      });
    }
    assert.deepEqual(routeForAppLinkUrl("fantappero://accedi/verifica?token=v"), {
      name: "AuthVerifyEmail",
      params: { token: "v" },
    });
    assert.deepEqual(routeForAppLinkUrl("fantappero:///accedi/reimposta-password?token=r"), {
      name: "AuthResetPassword",
      params: { token: "r" },
    });
    assert.ok(APP_LINK_PREFIXES.includes("https://www.fantappero.it"));
  });

  it("leaves other links alone (Google return, other sites, look-alike domains)", () => {
    assert.equal(routeForAppLinkUrl("fantappero://google-auth?code=x"), null);
    assert.equal(routeForAppLinkUrl("https://esempio.it/leghe/invito?token=x"), null);
    assert.equal(routeForAppLinkUrl("https://fantappero.it.esempio.it/leghe/invito?token=x"), null);
    assert.equal(routeForAppLinkUrl(null), null);
  });
});

describe("planAppLink", () => {
  const verify = routeForAppLinkUrl("fantappero://accedi/verifica?token=v");
  const invite = routeForAppLinkUrl("fantappero://leghe/invito?token=i");

  it("opens email verification and password reset only before login", () => {
    assert.deepEqual(planAppLink(verify, false), { kind: "open", route: verify });
    assert.deepEqual(planAppLink(verify, true), { kind: "ignore" });
  });

  it("opens the invite after login, or keeps it until the user logs in", () => {
    assert.deepEqual(planAppLink(invite, true), { kind: "open", route: invite });
    assert.deepEqual(planAppLink(invite, false), { kind: "after-login", route: invite });
    assert.deepEqual(planAppLink(null, true), { kind: "ignore" });
  });
});
