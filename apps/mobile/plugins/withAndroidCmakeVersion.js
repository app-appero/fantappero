const { withAppBuildGradle } = require("expo/config-plugins");

// AGP non specifica una versione di CMake: senza questo plugin usa il default
// (3.22.1), che include ninja 1.10.2. Su Windows ninja 1.10.2 non gestisce i
// percorsi lunghi, e il build nativo del codegen (react-native-safe-area-context,
// react-native-screens, sotto node_modules) genera percorsi oggetto oltre i 260
// caratteri: "ninja: error: Stat(...): Filename longer than 260 characters".
// CMake 4.1.2 include ninja 1.12.1, che li gestisce correttamente.
const CMAKE_VERSION = "4.1.2";

module.exports = function withAndroidCmakeVersion(config) {
  return withAppBuildGradle(config, (mod) => {
    if (mod.modResults.contents.includes("externalNativeBuild")) {
      return mod;
    }
    mod.modResults.contents = mod.modResults.contents.replace(
      "android {\n",
      `android {\n    externalNativeBuild {\n        cmake {\n            version "${CMAKE_VERSION}"\n        }\n    }\n\n`,
    );
    return mod;
  });
};
