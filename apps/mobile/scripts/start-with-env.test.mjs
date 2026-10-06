import assert from "node:assert/strict";
import { mkdtempSync, mkdirSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

import { resolveMobileProfile } from "./start-with-env.mjs";

const appRoot = join(dirname(fileURLToPath(import.meta.url)), "..");

test("pilota points at the Railway pilot API and the public Google client", () => {
  const resolved = resolveMobileProfile(appRoot, "pilota");
  assert.equal(resolved.apiUrl, "https://api-pilota.up.railway.app");
  assert.equal(resolved.env.EXPO_PUBLIC_WEB_BASE_URL, "https://fantappero-web-pilot.up.railway.app");
  assert.match(resolved.env.EXPO_PUBLIC_GOOGLE_CLIENT_ID_WEB, /\.apps\.googleusercontent\.com$/);
});

test("dev points at the Railway dev API", () => {
  const resolved = resolveMobileProfile(appRoot, "dev");
  assert.equal(resolved.apiUrl, "https://fantappero-api-dev.up.railway.app");
});

test("locale points at the local API", () => {
  const resolved = resolveMobileProfile(appRoot, "locale");
  assert.equal(resolved.apiUrl, "http://127.0.0.1:8001");
});

test("prod has no public origin yet", () => {
  assert.throws(
    () => resolveMobileProfile(appRoot, "prod"),
    /prod/,
  );
});

test("locale accepts a LAN override from .env.local", () => {
  const root = mkdtempSync(join(tmpdir(), "mobile-env-"));
  mkdirSync(join(root, "env"));
  writeFileSync(join(root, "env", "locale.env"), "EXPO_PUBLIC_API_BASE_URL=http://127.0.0.1:8001\n");
  writeFileSync(
    join(root, ".env.local"),
    "EXPO_PUBLIC_API_BASE_URL=http://192.168.1.20:8001\nEXPO_PUBLIC_GOOGLE_CLIENT_ID_WEB=web-id\n",
  );
  const resolved = resolveMobileProfile(root, "locale");
  assert.equal(resolved.apiUrl, "http://192.168.1.20:8001");
  assert.equal(resolved.env.EXPO_PUBLIC_GOOGLE_CLIENT_ID_WEB, "web-id");
});

test("pilota keeps the Railway URL even if .env.local has a LAN address", () => {
  const root = mkdtempSync(join(tmpdir(), "mobile-env-"));
  mkdirSync(join(root, "env"));
  writeFileSync(
    join(root, "env", "pilota.env"),
    "EXPO_PUBLIC_API_BASE_URL=https://api-pilota.up.railway.app\n",
  );
  writeFileSync(join(root, ".env.local"), "EXPO_PUBLIC_API_BASE_URL=http://192.168.1.20:8001\n");
  const resolved = resolveMobileProfile(root, "pilota");
  assert.equal(resolved.apiUrl, "https://api-pilota.up.railway.app");
});
