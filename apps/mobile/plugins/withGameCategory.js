const { withAndroidManifest } = require("expo/config-plugins");

/**
 * Dichiara l'app come "gioco" per Android (android:appCategory="game"):
 * il telefono può attivare la modalità gioco (Game Dashboard, prestazioni,
 * non disturbare) quando FantApperò è in primo piano.
 */
module.exports = function withGameCategory(config) {
  return withAndroidManifest(config, (mod) => {
    const application = mod.modResults.manifest.application?.[0];
    if (application) {
      application.$["android:appCategory"] = "game";
    }
    return mod;
  });
};
