import { describe, expect, it } from "vitest";
import { ANDROID_APP_PACKAGE, buildAssetLinks, parseFingerprints } from "./assetLinks";

const SHA = "FA:C6:17:45:DC:09:03:78:6F:B9:ED:E6:2A:96:2B:39:9F:73:48:F0:BB:6F:89:9B:83:32:66:75:91:03:3B:9C";

describe("assetLinks", () => {
  it("is absent when the environment has no fingerprint", () => {
    expect(buildAssetLinks(undefined)).toBeNull();
    expect(buildAssetLinks("  ")).toBeNull();
    expect(buildAssetLinks("non-una-impronta")).toBeNull();
  });

  it("declares the app package with every valid fingerprint", () => {
    expect(parseFingerprints(` ${SHA.toLowerCase()} , AB:CD`)).toEqual([SHA]);
    const parsed = JSON.parse(buildAssetLinks(SHA) ?? "[]");
    expect(parsed).toEqual([
      {
        relation: ["delegate_permission/common.handle_all_urls"],
        target: {
          namespace: "android_app",
          package_name: ANDROID_APP_PACKAGE,
          sha256_cert_fingerprints: [SHA],
        },
      },
    ]);
  });
});
