import assert from "node:assert/strict";
import { after, before, describe, it } from "node:test";

import { ApiError, createApiClient, getApiErrorMessage } from "./client.ts";

type FetchCall = { url: string; init: RequestInit | undefined };

function installFetchStub(handler: (url: string, init?: RequestInit) => Promise<Response> | Response) {
  const calls: FetchCall[] = [];
  const originalFetch = globalThis.fetch;
  globalThis.fetch = (async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    calls.push({ url, init });
    return handler(url, init);
  }) as typeof fetch;
  return {
    calls,
    restore: () => {
      globalThis.fetch = originalFetch;
    },
  };
}

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("createApiClient", () => {
  it("builds the request URL from resolveBaseUrl and forwards method/body/auth", async () => {
    const stub = installFetchStub(() => jsonResponse(200, { ok: true }));
    try {
      const { apiRequest } = createApiClient({
        resolveBaseUrl: () => "https://api.example.test",
        buildUploadValue: (file: string) => file,
      });
      const result = await apiRequest<{ ok: boolean }>("/ping", {
        body: { hello: "world" },
        accessToken: "tok123",
      });
      assert.deepEqual(result, { ok: true });
      assert.equal(stub.calls.length, 1);
      assert.equal(stub.calls[0]?.url, "https://api.example.test/ping");
      assert.equal(stub.calls[0]?.init?.method, "POST");
      const headers = stub.calls[0]?.init?.headers as Record<string, string>;
      assert.equal(headers.Authorization, "Bearer tok123");
      assert.equal(headers["Content-Type"], "application/json");
    } finally {
      stub.restore();
    }
  });

  it("returns undefined for 204 responses without parsing a body", async () => {
    const stub = installFetchStub(() => new Response(null, { status: 204 }));
    try {
      const { apiRequest } = createApiClient({
        resolveBaseUrl: () => "https://api.example.test",
        buildUploadValue: (file: string) => file,
      });
      const result = await apiRequest<void>("/void");
      assert.equal(result, undefined);
    } finally {
      stub.restore();
    }
  });

  it("throws ApiError with the string `detail` from a FastAPI error body", async () => {
    const stub = installFetchStub(() => jsonResponse(400, { detail: "Campo mancante" }));
    try {
      const { apiRequest } = createApiClient({
        resolveBaseUrl: () => "https://api.example.test",
        buildUploadValue: (file: string) => file,
      });
      await assert.rejects(apiRequest("/x"), (error: unknown) => {
        assert.ok(error instanceof ApiError);
        assert.equal(error.message, "Campo mancante");
        assert.equal(error.status, 400);
        return true;
      });
    } finally {
      stub.restore();
    }
  });

  it("throws ApiError with the first `msg` from an array-shaped `detail` (FastAPI validation errors)", async () => {
    const stub = installFetchStub(() =>
      jsonResponse(422, { detail: [{ msg: "Valore non valido" }, { msg: "altro" }] }),
    );
    try {
      const { apiRequest } = createApiClient({
        resolveBaseUrl: () => "https://api.example.test",
        buildUploadValue: (file: string) => file,
      });
      await assert.rejects(apiRequest("/x"), (error: unknown) => {
        assert.ok(error instanceof ApiError);
        assert.equal(error.message, "Valore non valido");
        assert.equal(error.status, 422);
        return true;
      });
    } finally {
      stub.restore();
    }
  });

  it("wraps a rejected fetch (offline/network failure) into an ApiError", async () => {
    const stub = installFetchStub(() => {
      throw new TypeError("Failed to fetch");
    });
    try {
      const { apiRequest } = createApiClient({
        resolveBaseUrl: () => "https://api.example.test",
        buildUploadValue: (file: string) => file,
      });
      await assert.rejects(apiRequest("/x"), (error: unknown) => {
        assert.ok(error instanceof ApiError);
        assert.equal(error.code, "network_error");
        assert.equal(error.message, "Connessione non disponibile. Riprova tra poco.");
        assert.equal(error.message.includes("https://api.example.test"), false);
        return true;
      });
    } finally {
      stub.restore();
    }
  });

  it("uses buildUploadValue to append the platform file to FormData", async () => {
    let capturedFormData: FormData | undefined;
    const stub = installFetchStub((_url, init) => {
      capturedFormData = init?.body as FormData;
      return jsonResponse(200, { ok: true });
    });
    try {
      const { apiUpload } = createApiClient<{ name: string }>({
        resolveBaseUrl: () => "https://api.example.test",
        buildUploadValue: (file) => `converted:${file.name}`,
      });
      await apiUpload("/upload", { accessToken: "tok", file: { name: "roster.csv" } });
      assert.equal(capturedFormData?.get("file"), "converted:roster.csv");
    } finally {
      stub.restore();
    }
  });

  it("invokes isDev-gated diagnostics only when isDev() returns true", async () => {
    const stub = installFetchStub(() => jsonResponse(500, {}));
    const originalError = console.error;
    let logCount = 0;
    console.error = () => {
      logCount += 1;
    };
    try {
      const { apiRequest } = createApiClient({
        resolveBaseUrl: () => "https://api.example.test",
        buildUploadValue: (file: string) => file,
        isDev: () => true,
      });
      await assert.rejects(apiRequest("/x"));
      assert.ok(logCount > 0);
    } finally {
      console.error = originalError;
      stub.restore();
    }
  });
});

describe("getApiErrorMessage", () => {
  it("uses the ApiError message when it is user-facing", () => {
    const error = new ApiError("Mercato chiuso.", 400, "market_closed");
    assert.equal(getApiErrorMessage(error, "Riprova."), "Mercato chiuso.");
  });

  it("hides backend setup instructions still present in an ApiError", () => {
    const error = new ApiError(
      "Impossibile aggiornare lo stato del mercato. Esegui la migrazione del database (alembic upgrade head).",
      400,
      "market_gate_unavailable",
    );
    assert.equal(
      getApiErrorMessage(error, "Impossibile aggiornare lo stato del mercato."),
      "Impossibile aggiornare lo stato del mercato.",
    );
  });

  it("does not surface raw Error messages such as SQL or env vars", () => {
    assert.equal(
      getApiErrorMessage(
        new Error("column leagues.market_open does not exist"),
        "Impossibile caricare le tue leghe.",
      ),
      "Impossibile caricare le tue leghe.",
    );
    assert.equal(
      getApiErrorMessage(
        new Error("Missing required environment variable: VITE_API_BASE_URL"),
        "Servizio non disponibile.",
      ),
      "Servizio non disponibile.",
    );
  });
});
