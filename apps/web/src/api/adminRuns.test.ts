import type { TurniBatch } from "@fantappero/contracts";
import { beforeEach, describe, expect, it, vi } from "vitest";

const apiRequestMock = vi.fn();
vi.mock("./client", () => ({
  apiRequest: (...args: unknown[]) => apiRequestMock(...args),
}));

import { runAllSystemJobs, runSystemJob, runTurniBatch } from "./admin";

function batch(status: string, ok: number): TurniBatch {
  return {
    batchId: "b/1",
    status,
    operations: [],
    ok,
    failed: 0,
    skipped: 0,
    startedAt: null,
    finishedAt: null,
  };
}

describe("«Esegui» e «Esegui tutti»: chiamate al server (1.5)", () => {
  beforeEach(() => {
    apiRequestMock.mockReset();
  });

  it("«Esegui» su un job è un POST su /admin/job/{chiave}/esegui", async () => {
    apiRequestMock.mockResolvedValue({ status: "started" });

    await runSystemJob("tok", "sports-poll-live");

    expect(apiRequestMock).toHaveBeenCalledWith("/admin/job/sports-poll-live/esegui", {
      accessToken: "tok",
      method: "POST",
    });
  });

  it("«Esegui tutti» nei Job è un POST su /admin/job/esegui-tutti", async () => {
    apiRequestMock.mockResolvedValue({ results: [] });

    await runAllSystemJobs("tok");

    expect(apiRequestMock).toHaveBeenCalledWith("/admin/job/esegui-tutti", {
      accessToken: "tok",
      method: "POST",
    });
  });

  it("«Esegui tutti» nei Turni avvia il blocco e lo rilegge finché non è finito", async () => {
    apiRequestMock
      .mockResolvedValueOnce(batch("queued", 0))
      .mockResolvedValueOnce(batch("running", 2))
      .mockResolvedValueOnce(batch("completed", 5));
    const seen: string[] = [];

    const result = await runTurniBatch("tok", {
      pollIntervalMs: 1,
      onProgress: (state) => seen.push(`${state.status}:${state.ok}`),
    });

    expect(result.status).toBe("completed");
    expect(seen).toEqual(["queued:0", "running:2", "completed:5"]);
    expect(apiRequestMock.mock.calls[0]).toEqual([
      "/admin/turni/esegui-tutti",
      { accessToken: "tok", method: "POST" },
    ]);
    expect(apiRequestMock.mock.calls[1]).toEqual([
      "/admin/turni/esegui-tutti/b%2F1",
      { accessToken: "tok" },
    ]);
  });
});
