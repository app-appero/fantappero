import { spawn } from "node:child_process";
import { existsSync, readFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

export const MOBILE_PROFILES = ["locale", "dev", "pilota", "prod"];

const PROFILE_KEYS = [
  "EXPO_PUBLIC_GOOGLE_CLIENT_ID_WEB",
  "EXPO_PUBLIC_GOOGLE_CLIENT_ID_ANDROID",
  "EXPO_PUBLIC_WEB_BASE_URL",
];

export function parseEnvFile(path) {
  if (!existsSync(path)) {
    return {};
  }
  const values = {};
  for (const line of readFileSync(path, "utf8").split("\n")) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith("#")) {
      continue;
    }
    const eq = trimmed.indexOf("=");
    if (eq <= 0) {
      continue;
    }
    const key = trimmed.slice(0, eq).trim();
    let value = trimmed.slice(eq + 1).trim();
    if (
      (value.startsWith('"') && value.endsWith('"')) ||
      (value.startsWith("'") && value.endsWith("'"))
    ) {
      value = value.slice(1, -1);
    }
    values[key] = value;
  }
  return values;
}

export function resolveMobileProfile(appRoot, profile) {
  if (!MOBILE_PROFILES.includes(profile)) {
    throw new Error(`Profilo sconosciuto "${profile}". Usa: ${MOBILE_PROFILES.join(", ")}.`);
  }
  const profileVars = parseEnvFile(join(appRoot, "env", `${profile}.env`));
  const localVars = parseEnvFile(join(appRoot, ".env.local"));
  const fromProfile = profileVars.EXPO_PUBLIC_API_BASE_URL?.trim() ?? "";
  const fromLocal = localVars.EXPO_PUBLIC_API_BASE_URL?.trim() ?? "";
  const apiUrl = (profile === "locale" ? fromLocal : "") || fromProfile;
  if (!apiUrl) {
    throw new Error(
      `Il profilo "${profile}" non ha EXPO_PUBLIC_API_BASE_URL. ` +
        `Quando l'origine pubblica esiste, scrivila in apps/mobile/env/${profile}.env.`,
    );
  }
  const env = { EXPO_PUBLIC_API_BASE_URL: apiUrl };
  for (const key of PROFILE_KEYS) {
    const value = (localVars[key] || profileVars[key] || "").trim();
    if (value) {
      env[key] = value;
    }
  }
  return { profile, apiUrl, env };
}

function appRootFromHere() {
  return join(dirname(fileURLToPath(import.meta.url)), "..");
}

// Expo's shared ngrok account rejects new agents with ERR_NGROK_108, and
// @expo/ngrok then crashes on a missing response body. The websocket tunnel
// (the same one Expo uses outside ngrok) only accepts local port 8081.
export function expoLaunchSpec() {
  return {
    command: "pnpm",
    args: ["exec", "expo", "start", "--tunnel", "--port", "8081", "-c"],
    env: {
      EXPO_FORCE_WEBCONTAINER_ENV: "1",
      EXPO_UNSTABLE_HEADLESS: "0",
    },
  };
}

function runExpo(appRoot, env) {
  const launch = expoLaunchSpec();
  const child = spawn(launch.command, launch.args, {
    cwd: appRoot,
    env: { ...process.env, ...env, ...launch.env },
    stdio: "inherit",
  });
  child.on("exit", (code, signal) => {
    if (signal) {
      process.kill(process.pid, signal);
      return;
    }
    process.exit(code ?? 1);
  });
}

const isDirectRun =
  Boolean(process.argv[1]) && resolve(process.argv[1]) === fileURLToPath(import.meta.url);

if (isDirectRun) {
  const profile = process.argv[2];
  const appRoot = appRootFromHere();
  let resolved;
  try {
    resolved = resolveMobileProfile(appRoot, profile);
  } catch (error) {
    console.error(error instanceof Error ? error.message : String(error));
    process.exit(1);
  }
  console.log(`FantApperò mobile · ${resolved.profile} · ${resolved.apiUrl}`);
  console.log("Tunnel Expo attivo: il QR punta a boltexpo.dev e si apre da Expo Go su qualsiasi rete.");
  if (process.argv.includes("--print")) {
    process.exit(0);
  }
  runExpo(appRoot, resolved.env);
}
