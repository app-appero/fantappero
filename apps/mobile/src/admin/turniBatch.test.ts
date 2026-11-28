import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { describe, it } from "node:test";
import { fileURLToPath } from "node:url";
import type { TurniBatch } from "@fantappero/contracts";
import {
  CONFIRM_CANCEL_LABEL,
  CONFIRM_TITLE,
} from "../../../../packages/contracts/src/confirmations.ts";
import {
  RUN_ALL_LABEL,
  jobRunConfirmation,
  jobsRunAllConfirmation,
  turniBatchConfirmation,
} from "../../../../packages/contracts/src/operatorRuns.ts";
import { pollTurniBatch, type TurniBatchApi } from "./turniBatch.ts";

function batch(status: string, ok: number, overrides: Partial<TurniBatch> = {}): TurniBatch {
  return {
    batchId: "b1",
    status,
    operations: [],
    ok,
    failed: 0,
    skipped: 0,
    startedAt: null,
    finishedAt: null,
    ...overrides,
  };
}

function fakeApi(states: TurniBatch[]) {
  const calls: string[] = [];
  const queue = [...states];
  const api: TurniBatchApi = {
    async start() {
      calls.push("start");
      return queue.shift() as TurniBatch;
    },
    async fetch(batchId: string) {
      calls.push(`fetch:${batchId}`);
      return queue.shift() as TurniBatch;
    },
  };
  return { api, calls };
}

describe("«Esegui tutti» nei Turni dell'app (1.5): lettura dell'avanzamento", () => {
  it("avvia il blocco, rilegge finché non è finito e restituisce l'ultimo stato", async () => {
    const { api, calls } = fakeApi([
      batch("queued", 0),
      batch("running", 2),
      batch("completed", 5),
    ]);
    const seen: string[] = [];
    const sleeps: number[] = [];

    const result = await pollTurniBatch(api, {
      onProgress: (state) => seen.push(`${state.status}:${state.ok}`),
      pollIntervalMs: 250,
      sleep: async (ms) => {
        sleeps.push(ms);
      },
    });

    assert.equal(result.status, "completed");
    assert.deepEqual(calls, ["start", "fetch:b1", "fetch:b1"]);
    assert.deepEqual(seen, ["queued:0", "running:2", "completed:5"]);
    assert.deepEqual(sleeps, [250, 250]);
  });

  it("se il blocco è già finito alla prima risposta non rilegge nulla", async () => {
    const { api, calls } = fakeApi([batch("completed", 5)]);

    const result = await pollTurniBatch(api, { sleep: async () => undefined });

    assert.equal(result.ok, 5);
    assert.deepEqual(calls, ["start"]);
  });

  it("un blocco interrotto (failed) finisce l'attesa", async () => {
    const { api } = fakeApi([batch("running", 1), batch("failed", 1, { failed: 4 })]);

    const result = await pollTurniBatch(api, { sleep: async () => undefined });

    assert.equal(result.status, "failed");
    assert.equal(result.failed, 4);
  });

  it("un errore all'avvio (es. già in corso, 409) arriva a chi chiama", async () => {
    const api: TurniBatchApi = {
      async start() {
        throw new Error("Le operazioni dei turni sono già in corso.");
      },
      async fetch() {
        throw new Error("non dovrebbe essere chiamata");
      },
    };

    await assert.rejects(pollTurniBatch(api), /già in corso/);
  });
});

describe("«Sei sicuro?» dell'app: gli stessi testi del sito (1.5)", () => {
  it("titolo e «Annulla» sono quelli delle altre finestre", () => {
    for (const copy of [
      turniBatchConfirmation(),
      jobRunConfirmation({ title: "A", enabled: true, usesProviderQuota: false, sendsNotifications: false }),
    ]) {
      assert.equal(copy.title, CONFIRM_TITLE);
      assert.equal(copy.cancelLabel, CONFIRM_CANCEL_LABEL);
    }
    assert.equal(turniBatchConfirmation().confirmLabel, RUN_ALL_LABEL);
    assert.equal(
      jobsRunAllConfirmation([
        { title: "A", enabled: true, usesProviderQuota: true, sendsNotifications: false },
      ])?.confirmLabel,
      RUN_ALL_LABEL,
    );
  });
});

describe("schermate dell'app: «Esegui» e «Esegui tutti» (1.5)", () => {
  const here = dirname(fileURLToPath(import.meta.url));
  const jobs = readFileSync(join(here, "../screens/admin/AdminJobsScreen.tsx"), "utf8");
  const turni = readFileSync(join(here, "../screens/admin/AdminTurniScreen.tsx"), "utf8");
  const api = readFileSync(join(here, "../api/admin.ts"), "utf8");

  it("usano ConfirmDialog e mai Alert.alert (nel browser non si apre)", () => {
    for (const source of [jobs, turni]) {
      assert.match(source, /<ConfirmDialog/);
      assert.doesNotMatch(source, /Alert\.alert/);
    }
  });

  it("Job: «Esegui» su ogni job e «Esegui tutti» in cima", () => {
    assert.match(jobs, /testID="admin-jobs-run-all"/);
    assert.match(jobs, /testID=\{`admin-job-run-\$\{job\.key\}`\}/);
    assert.match(jobs, /RUN_JOB_LABEL/);
    assert.match(jobs, /RUN_ALL_LABEL/);
    assert.match(jobs, /jobsRunAllConfirmation\(jobs\)/);
    assert.match(jobs, /jobRunConfirmation\(pendingRun\.job\)/);
  });

  it("Job: un job già in corso non si rilancia dal pulsante", () => {
    assert.match(jobs, /disabled=\{runBusy !== null \|\| job\.running\}/);
  });

  it("Turni: «Esegui tutti» con la finestra dei testi condivisi e l'esito per operazione", () => {
    assert.match(turni, /testID="admin-turni-run-all"/);
    assert.match(turni, /turniBatchConfirmation\(\)/);
    assert.match(turni, /turniBatchOperationOutcome/);
    assert.match(turni, /runTurniBatch\(accessToken/);
  });

  it("le chiamate al server sono quelle degli endpoint nuovi", () => {
    assert.match(api, /`\/admin\/job\/\$\{encodeURIComponent\(jobKey\)\}\/esegui`/);
    assert.match(api, /"\/admin\/job\/esegui-tutti"/);
    assert.match(api, /"\/admin\/turni\/esegui-tutti"/);
  });
});
