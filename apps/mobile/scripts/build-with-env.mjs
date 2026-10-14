import { spawnSync } from "node:child_process";
import { copyFileSync, existsSync, rmSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { resolveMobileProfile } from "./start-with-env.mjs";

function appRootFromHere() {
  return join(dirname(fileURLToPath(import.meta.url)), "..");
}

const profile = process.argv[2];
const variant = process.argv[3] ?? "release";

if (!["debug", "release"].includes(variant)) {
  console.error(`Variante sconosciuta "${variant}". Usa: debug, release.`);
  process.exit(1);
}

const appRoot = appRootFromHere();
let resolved;
try {
  resolved = resolveMobileProfile(appRoot, profile);
} catch (error) {
  console.error(error instanceof Error ? error.message : String(error));
  process.exit(1);
}

console.log(`FantApperò mobile · build APK ${variant} · ${resolved.profile} · ${resolved.apiUrl}`);

const androidDir = join(appRoot, "android");

// La cartella android/ è generata (non versionata): senza rigenerarla restano
// nome e icona di una build precedente. `prebuild` (senza --clean) la aggiorna
// da app.json (nome, icona, icona adattiva) prima di compilare.
const prebuild = spawnSync("npx", ["expo", "prebuild", "--platform", "android", "--no-install"], {
  cwd: appRoot,
  stdio: "inherit",
  shell: process.platform === "win32",
});
if (prebuild.status !== 0) {
  process.exit(prebuild.status ?? 1);
}
const gradlew = process.platform === "win32" ? ".\\gradlew.bat" : "./gradlew";
const task = variant === "release" ? "assembleRelease" : "assembleDebug";

// Il task Gradle che genera il bundle JS (createBundle<Variant>JsAndAssets) non
// dichiara le env var tra i suoi input, quindi Gradle lo considera "up-to-date"
// anche quando cambia il profilo (.env) e riusa un bundle vecchio con le
// EXPO_PUBLIC_* sbagliate o mancanti. Cancelliamo i suoi output dichiarati per
// forzare una rigenerazione del bundle ad ogni build.
const bundleOutputDirs = [
  join(androidDir, "app", "build", "generated", "assets", "react", variant),
  join(androidDir, "app", "build", "generated", "res", "react", variant),
  join(androidDir, "app", "build", "generated", "sourcemaps", "react", variant),
  join(androidDir, "app", "build", "intermediates", "sourcemaps", "react", variant),
];
for (const dir of bundleOutputDirs) {
  rmSync(dir, { recursive: true, force: true });
}

// --no-daemon: il daemon Gradle riusa il processo tra le build e manterrebbe
// le env var del profilo precedente se restasse acceso.
const result = spawnSync(gradlew, [task, "--no-daemon"], {
  cwd: androidDir,
  env: { ...process.env, ...resolved.env },
  stdio: "inherit",
  shell: process.platform === "win32",
});

if (result.status === 0) {
  // Gradle produce app-<variante>.apk: ne lasciamo anche una copia con il nome dell'app.
  const apkDir = join(androidDir, "app", "build", "outputs", "apk", variant);
  const built = join(apkDir, `app-${variant}.apk`);
  if (existsSync(built)) {
    const named = join(apkDir, `FantApperò-${variant}.apk`);
    copyFileSync(built, named);
    console.log(`APK: ${named}`);
  }
}

process.exit(result.status ?? 1);
