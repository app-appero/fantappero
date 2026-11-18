const { withAndroidManifest } = require("expo/config-plugins");

/**
 * App Link Android: i link web delle email (verifica email, nuova password, invito in lega)
 * aprono l'app invece del browser, quando l'app è installata.
 *
 * I domini cambiano per ambiente e arrivano da EXPO_PUBLIC_APP_LINK_HOSTS (env/<profilo>.env,
 * separati da virgola): dev → dev.fantappero.it, pilota → pilota.fantappero.it,
 * produzione → fantappero.it e www.fantappero.it. Senza la variabile non si aggiunge nulla.
 *
 * android:autoVerify: Android apre i link senza chiedere solo se il sito pubblica
 * /.well-known/assetlinks.json con l'impronta del certificato dell'APK
 * (apps/web/public/.well-known/assetlinks.json).
 */
const PATH_PREFIXES = ["/accedi/verifica", "/accedi/reimposta-password", "/leghe/invito"];

function appLinkHosts() {
  return (process.env.EXPO_PUBLIC_APP_LINK_HOSTS ?? "")
    .split(",")
    .map((host) => host.trim().toLowerCase())
    .filter((host) => /^[a-z0-9.-]+$/.test(host));
}

/** Il filtro aggiunto da questo plugin (riconosciuto dai percorsi, nel manifest non ci sono marcatori). */
function isAppLinkFilter(filter) {
  return (filter.data ?? []).some((item) => PATH_PREFIXES.includes(item.$?.["android:pathPrefix"]));
}

function buildIntentFilter(hosts) {
  return {
    $: { "android:autoVerify": "true" },
    action: [{ $: { "android:name": "android.intent.action.VIEW" } }],
    category: [
      { $: { "android:name": "android.intent.category.DEFAULT" } },
      { $: { "android:name": "android.intent.category.BROWSABLE" } },
    ],
    data: [
      { $: { "android:scheme": "https" } },
      ...hosts.map((host) => ({ $: { "android:host": host } })),
      ...PATH_PREFIXES.map((prefix) => ({ $: { "android:pathPrefix": prefix } })),
    ],
  };
}

module.exports = function withAppLinks(config) {
  return withAndroidManifest(config, (mod) => {
    const hosts = appLinkHosts();
    const activity = mod.modResults.manifest.application?.[0]?.activity?.find(
      (item) => item.$?.["android:name"] === ".MainActivity",
    );
    if (!activity) {
      return mod;
    }
    // prebuild senza --clean riusa il manifest: si toglie il filtro della build precedente.
    activity["intent-filter"] = (activity["intent-filter"] ?? []).filter(
      (filter) => !isAppLinkFilter(filter),
    );
    if (hosts.length > 0) {
      activity["intent-filter"].push(buildIntentFilter(hosts));
    }
    return mod;
  });
};

module.exports.appLinkHosts = appLinkHosts;
module.exports.buildIntentFilter = buildIntentFilter;
module.exports.isAppLinkFilter = isAppLinkFilter;
