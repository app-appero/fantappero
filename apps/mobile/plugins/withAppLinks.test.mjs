import assert from "node:assert/strict";
import { createRequire } from "node:module";
import { describe, it } from "node:test";

const require = createRequire(import.meta.url);
const plugin = require("./withAppLinks.js");

describe("withAppLinks", () => {
  it("reads the hosts of the profile and drops malformed ones", () => {
    process.env.EXPO_PUBLIC_APP_LINK_HOSTS = " Dev.Fantappero.it , bad host,,www.fantappero.it";
    assert.deepEqual(plugin.appLinkHosts(), ["dev.fantappero.it", "www.fantappero.it"]);
    delete process.env.EXPO_PUBLIC_APP_LINK_HOSTS;
    assert.deepEqual(plugin.appLinkHosts(), []);
  });

  it("builds a verified https filter limited to the email link paths", () => {
    const filter = plugin.buildIntentFilter(["fantappero.it", "www.fantappero.it"]);
    assert.equal(filter.$["android:autoVerify"], "true");
    const data = filter.data.map((item) => item.$);
    assert.deepEqual(data[0], { "android:scheme": "https" });
    assert.ok(data.some((item) => item["android:host"] === "www.fantappero.it"));
    assert.deepEqual(
      data.filter((item) => item["android:pathPrefix"]).map((item) => item["android:pathPrefix"]),
      ["/accedi/verifica", "/accedi/reimposta-password", "/leghe/invito"],
    );
    assert.ok(plugin.isAppLinkFilter(filter));
    assert.ok(!plugin.isAppLinkFilter({ data: [{ $: { "android:scheme": "fantappero" } }] }));
  });
});
