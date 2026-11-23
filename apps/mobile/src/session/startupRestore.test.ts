import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { describe, it } from "node:test";
import {
  OFFLINE_RETRY_INTERVAL_MS,
  restoreSessionAtStartup,
  startupGate,
  type StartupRestoreDeps,
} from "./startupRestore.ts";

type Session = { accessToken: string; refreshToken: string; user: { id: string; displayName: string } };

class FakeApiError extends Error {
  readonly status: number;
  readonly code: string;
  constructor(status: number, code: string) {
    super(code);
    this.status = status;
    this.code = code;
  }
}
const networkError = () => new FakeApiError(0, "network_error");
const unauthorized = () => new FakeApiError(401, "unauthorized");

const user = { id: "u1", displayName: "Rosario" };
const stored: Session = { accessToken: "a1", refreshToken: "r1", user };

/** Archivio e API finti: `me` e `refresh` decidono come risponde il server. */
function fakeDeps(options: {
  stored?: Session | null;
  me: () => Promise<typeof user>;
  refresh?: () => Promise<string | null>;
  operator?: Session | null;
}) {
  let memory: Session | null = options.stored === undefined ? stored : options.stored;
  const calls: string[] = [];
  const deps = {
    loadStoredSession: async () => memory,
    fetchMe: async () => options.me(),
    getMemorySession: () => memory,
    isTransientError: (error: unknown) =>
      error instanceof FakeApiError && (error.status === 0 || error.status >= 500 || error.code === "network_error"),
    loadImpersonatorSession: async () => options.operator ?? null,
    clearImpersonatorSession: async () => {
      calls.push("clearImpersonator");
    },
    forgetSession: async () => {
      calls.push("forget");
      memory = null;
    },
    refreshStoredSession: async () => {
      calls.push("refresh");
      const token = await (options.refresh ?? (async () => null))();
      if (token && memory) {
        memory = { ...memory, accessToken: token };
      }
      return token;
    },
  } as unknown as StartupRestoreDeps;
  return { deps, calls, memory: () => memory };
}

describe("avvio dell'app senza rete (corsa M5, 22/11)", () => {
  it("rete assente: «offline» e la sessione resta salvata, nessun accesso da rifare", async () => {
    const { deps, calls, memory } = fakeDeps({ me: async () => Promise.reject(networkError()) });
    assert.deepEqual(await restoreSessionAtStartup(deps), { kind: "offline" });
    assert.deepEqual(calls, []);
    assert.equal(memory()?.refreshToken, "r1");
  });

  it("tornata la rete, il nuovo tentativo entra con la stessa sessione", async () => {
    let online = false;
    const { deps } = fakeDeps({ me: async () => (online ? user : Promise.reject(networkError())) });
    assert.equal((await restoreSessionAtStartup(deps)).kind, "offline");
    online = true;
    assert.deepEqual(await restoreSessionAtStartup(deps), {
      kind: "signedIn",
      session: { ...stored, user },
      persist: true,
    });
  });

  it("server giù (5xx) durante il rinnovo: anche questo è «offline», non un logout", async () => {
    const { deps, calls } = fakeDeps({
      me: async () => Promise.reject(unauthorized()),
      refresh: async () => Promise.reject(new FakeApiError(503, "service_unavailable")),
    });
    assert.deepEqual(await restoreSessionAtStartup(deps), { kind: "offline" });
    assert.deepEqual(calls, ["refresh"]);
  });
});

describe("ripresa della sessione all'avvio (comportamento di prima)", () => {
  it("nessuna sessione salvata: accesso", async () => {
    const { deps } = fakeDeps({ stored: null, me: async () => user });
    assert.deepEqual(await restoreSessionAtStartup(deps), { kind: "signedOut" });
  });

  it("token scaduto: rinnovo e ingresso", async () => {
    const { deps } = fakeDeps({ me: async () => Promise.reject(unauthorized()), refresh: async () => "a2" });
    const outcome = await restoreSessionAtStartup(deps);
    assert.equal(outcome.kind, "signedIn");
    assert.equal(outcome.kind === "signedIn" && outcome.session.accessToken, "a2");
  });

  it("refresh token rifiutato: sessione cancellata e accesso", async () => {
    const { deps, calls } = fakeDeps({
      me: async () => Promise.reject(unauthorized()),
      refresh: async () => Promise.reject(unauthorized()),
    });
    assert.deepEqual(await restoreSessionAtStartup(deps), { kind: "signedOut" });
    assert.deepEqual(calls, ["refresh", "forget"]);
  });

  it("impersonificazione scaduta: si torna alla sessione dell'operatore", async () => {
    const operator: Session = { accessToken: "op", refreshToken: "op-r", user: { id: "op", displayName: "Operatore" } };
    const { deps, calls } = fakeDeps({
      stored: { ...stored, refreshToken: "" },
      me: async () => Promise.reject(unauthorized()),
      operator,
    });
    assert.deepEqual(await restoreSessionAtStartup(deps), { kind: "signedIn", session: operator, persist: true });
    assert.deepEqual(calls, ["clearImpersonator"]);
  });
});

describe("radice della navigazione", () => {
  it("offline senza sessione attiva mostra «Connessione non disponibile», non l'accesso", () => {
    assert.equal(startupGate({ loading: true, isAuthenticated: false, sessionOffline: false }), "loading");
    assert.equal(startupGate({ loading: false, isAuthenticated: false, sessionOffline: true }), "offline");
    assert.equal(startupGate({ loading: false, isAuthenticated: false, sessionOffline: false }), "auth");
    assert.equal(startupGate({ loading: false, isAuthenticated: true, sessionOffline: false }), "app");
  });

  it("la radice usa il cancello, la sessione riprova da sola e al ritorno in primo piano", () => {
    const root = readFileSync(new URL("../navigation/RootNavigator.tsx", import.meta.url), "utf8");
    assert.match(root, /startupGate\(\{ loading, isAuthenticated, sessionOffline \}\)/);
    assert.match(root, /Connessione non disponibile/);
    assert.match(root, /testID="auth-offline-retry"/);
    const session = readFileSync(new URL("./DemoSessionContext.tsx", import.meta.url), "utf8");
    assert.match(session, /restoreSessionAtStartup\(\{/);
    assert.match(session, /setInterval\(\(\) => \{\n\s*void restoreSession\(\);\n\s*\}, OFFLINE_RETRY_INTERVAL_MS\)/);
    assert.ok(OFFLINE_RETRY_INTERVAL_MS > 0 && OFFLINE_RETRY_INTERVAL_MS <= 10_000);
  });
});
