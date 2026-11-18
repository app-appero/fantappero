/**
 * /.well-known/assetlinks.json per gli App Link Android (apps/mobile/plugins/withAppLinks.js):
 * Android apre nell'app i link delle email solo se il sito dichiara il pacchetto e l'impronta
 * SHA-256 del certificato con cui è firmato l'APK.
 *
 * Le impronte arrivano da ANDROID_APP_LINK_SHA256 (variabile del servizio web, per ambiente,
 * separate da virgola). Senza variabile il file non esiste e i link restano pagine web.
 */
export const ANDROID_APP_PACKAGE = "com.fantappero.mobile";
export const ASSET_LINKS_PATH = "/.well-known/assetlinks.json";

const FINGERPRINT = /^([0-9A-F]{2}:){31}[0-9A-F]{2}$/;

export function parseFingerprints(raw: string | undefined): string[] {
  return (raw ?? "")
    .split(",")
    .map((value) => value.trim().toUpperCase())
    .filter((value) => FINGERPRINT.test(value));
}

/** Il contenuto del file, o null se l'ambiente non ha impronte valide. */
export function buildAssetLinks(raw: string | undefined): string | null {
  const fingerprints = parseFingerprints(raw);
  if (fingerprints.length === 0) {
    return null;
  }
  return JSON.stringify([
    {
      relation: ["delegate_permission/common.handle_all_urls"],
      target: {
        namespace: "android_app",
        package_name: ANDROID_APP_PACKAGE,
        sha256_cert_fingerprints: fingerprints,
      },
    },
  ]);
}
