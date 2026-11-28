import assert from "node:assert/strict";
import { describe, it } from "node:test";
import type { SystemJob, SystemJobRunAllResult, SystemJobRunResult, TurniBatch } from "./admin.ts";
import { CONFIRM_CANCEL_LABEL, CONFIRM_TITLE } from "./confirmations.ts";
import {
  PROVIDER_QUOTA_NOTE,
  RUN_ALL_LABEL,
  RUN_JOB_LABEL,
  TURNI_BATCH_OPERATIONS,
  isTurniBatchFinished,
  jobLastRunLabel,
  jobRunConfirmation,
  jobRunOutcome,
  jobsRunAllConfirmation,
  jobsRunAllSummary,
  jobsRunAllTone,
  runnableJobs,
  turniBatchConfirmation,
  turniBatchOperationOutcome,
  turniBatchSummary,
  turniBatchTone,
} from "./operatorRuns.ts";

function job(overrides: Partial<SystemJob> = {}): SystemJob {
  return {
    key: "sports-data-sync-fixtures",
    title: "Calendario partite",
    description: "",
    task: "sports_data.sync_mvp_fixtures",
    enabled: true,
    intervalSeconds: 3600,
    minIntervalSeconds: 60,
    maxIntervalSeconds: 86400,
    lastStartedAt: null,
    nextRunAt: null,
    usesProviderQuota: false,
    sendsNotifications: false,
    running: false,
    lastRun: null,
    ...overrides,
  };
}

function runResult(overrides: Partial<SystemJobRunResult> = {}): SystemJobRunResult {
  return {
    key: "k",
    title: "Calendario partite",
    status: "started",
    message: "«Calendario partite» lanciato: il giro è in coda e parte tra poco.",
    warning: null,
    code: null,
    taskId: "t",
    ...overrides,
  };
}

function batch(overrides: Partial<TurniBatch> = {}): TurniBatch {
  return {
    batchId: "b",
    status: "completed",
    operations: TURNI_BATCH_OPERATIONS.map((op) => ({
      key: op.key,
      label: op.label,
      status: "ok",
      message: null,
    })),
    ok: 5,
    failed: 0,
    skipped: 0,
    startedAt: null,
    finishedAt: null,
    ...overrides,
  };
}

describe("«Sei sicuro?» di Esegui tutti nei Turni", () => {
  it("usa gli stessi titolo e «Annulla» delle altre finestre", () => {
    const copy = turniBatchConfirmation();
    assert.equal(copy.title, CONFIRM_TITLE);
    assert.equal(copy.cancelLabel, CONFIRM_CANCEL_LABEL);
    assert.equal(copy.confirmLabel, RUN_ALL_LABEL);
  });

  it("elenca le operazioni nell'ordine in cui girano", () => {
    const { message } = turniBatchConfirmation();
    const positions = TURNI_BATCH_OPERATIONS.map((op) => message.indexOf(`• ${op.label}`));
    assert.ok(positions.every((position) => position >= 0));
    assert.deepEqual([...positions].sort((a, b) => a - b), positions);
    assert.deepEqual(
      TURNI_BATCH_OPERATIONS.map((op) => op.key),
      [
        "importa-stagione",
        "genera-calendario",
        "sincronizza-turni",
        "formazioni-probabili",
        "formazioni-ia",
      ],
    );
  });

  it("avvisa che alcune usano la quota del fornitore e dice quali", () => {
    const { message } = turniBatchConfirmation();
    assert.match(message, new RegExp(PROVIDER_QUOTA_NOTE));
    assert.match(
      message,
      /quota del fornitore sportivo: Importa calendario stagione, Genera calendario, Aggiorna probabili\./,
    );
    assert.doesNotMatch(message, /quota del fornitore sportivo:.*Sincronizza turni/);
  });

  it("dice che un errore non ferma le altre e che non omologa né ricalcola lo storico", () => {
    const { message } = turniBatchConfirmation();
    assert.match(message, /le altre vanno avanti/);
    assert.match(message, /Non omologa nessun turno e non ricalcola lo storico/);
  });

  it("non offre le operazioni a senso unico", () => {
    const labels = TURNI_BATCH_OPERATIONS.map((op) => op.label.toLowerCase()).join("|");
    for (const excluded of ["calcola giornata", "recupera", "ricalcola", "omologa"]) {
      assert.ok(!labels.includes(excluded), excluded);
    }
  });
});

describe("«Sei sicuro?» di Esegui su un job", () => {
  it("lancia una volta sola e usa il pulsante «Esegui»", () => {
    const copy = jobRunConfirmation(job());
    assert.equal(copy.title, CONFIRM_TITLE);
    assert.equal(copy.confirmLabel, RUN_JOB_LABEL);
    assert.equal(copy.cancelLabel, CONFIRM_CANCEL_LABEL);
    assert.equal(copy.message, "Lancio «Calendario partite» adesso, una volta sola.");
  });

  it("avvisa della quota del fornitore solo per i job che la usano", () => {
    assert.match(jobRunConfirmation(job({ usesProviderQuota: true })).message, /quota del fornitore/);
    assert.doesNotMatch(jobRunConfirmation(job()).message, /quota del fornitore/);
  });

  it("avvisa che un job spento parte lo stesso una volta sola", () => {
    const message = jobRunConfirmation(job({ enabled: false })).message;
    assert.match(message, /Il job è spento: parte lo stesso questa volta, poi resta spento/);
  });

  it("avvisa degli avvisi ai fantallenatori", () => {
    assert.match(
      jobRunConfirmation(job({ sendsNotifications: true })).message,
      /avvisi ai fantallenatori/,
    );
  });
});

describe("«Sei sicuro?» di Esegui tutti nei Job", () => {
  it("elenca solo i job accesi e dice che gli spenti restano fuori", () => {
    const copy = jobsRunAllConfirmation([
      job({ title: "A" }),
      job({ title: "B", enabled: false }),
      job({ title: "C" }),
    ]);
    assert.ok(copy);
    assert.equal(copy.confirmLabel, RUN_ALL_LABEL);
    assert.match(copy.message, /Lancio ora tutti i 2 job attivi, una volta sola:\n• A\n• C\n/);
    assert.doesNotMatch(copy.message, /• B/);
    assert.match(copy.message, /Un job già in esecuzione non si rilancia\. I job spenti restano fuori\./);
  });

  it("avvisa della quota per i soli job che la usano, con i loro nomi", () => {
    const message = jobsRunAllConfirmation([
      job({ title: "Risultati live", usesProviderQuota: true }),
      job({ title: "Avvisi programmati", sendsNotifications: true }),
      job({ title: "Formazioni probabili", usesProviderQuota: true }),
    ])!.message;
    assert.match(
      message,
      /Alcuni usano la quota del fornitore sportivo: Risultati live, Formazioni probabili\./,
    );
    assert.match(message, /Questo può mandare avvisi ai fantallenatori: Avvisi programmati\./);
  });

  it("non avvisa della quota se nessun job la usa", () => {
    const message = jobsRunAllConfirmation([job({ title: "A" }), job({ title: "B" })])!.message;
    assert.doesNotMatch(message, /quota/);
  });

  it("al singolare con un solo job acceso", () => {
    const message = jobsRunAllConfirmation([job({ title: "Solo" })])!.message;
    assert.match(message, /^Lancio ora il job attivo, una volta sola:\n• Solo\n/);
  });

  it("senza job accesi non c'è nulla da confermare", () => {
    assert.equal(jobsRunAllConfirmation([job({ enabled: false })]), null);
    assert.equal(jobsRunAllConfirmation([]), null);
    assert.deepEqual(runnableJobs([job(), job({ enabled: false })]).length, 1);
  });
});

describe("esito per job", () => {
  it("avviato: verde; con l'avviso del job spento diventa giallo e lo riporta", () => {
    assert.equal(jobRunOutcome(runResult()).tone, "success");
    const warned = jobRunOutcome(
      runResult({ warning: "«Calendario partite» è spento: l'ho lanciato a mano una volta sola." }),
    );
    assert.equal(warned.tone, "warning");
    assert.match(warned.text, /è spento: l'ho lanciato a mano una volta sola/);
    assert.match(warned.text, /lanciato: il giro è in coda/);
  });

  it("già in esecuzione: giallo, con il messaggio chiaro", () => {
    const line = jobRunOutcome(
      runResult({ status: "already_running", message: "«Calendario partite» è già in esecuzione: non lo rilancio." }),
    );
    assert.equal(line.tone, "warning");
    assert.match(line.text, /già in esecuzione/);
  });

  it("non partito: rosso", () => {
    assert.equal(jobRunOutcome(runResult({ status: "failed", message: "Non lanciato." })).tone, "error");
  });

  it("riepilogo con singolare e plurale", () => {
    const summary = (started: number, alreadyRunning: number, failed: number): SystemJobRunAllResult => ({
      results: [],
      started,
      alreadyRunning,
      failed,
    });
    assert.equal(jobsRunAllSummary(summary(9, 0, 0)), "Avviati 9 job su 9.");
    assert.equal(
      jobsRunAllSummary(summary(8, 1, 0)),
      "Avviati 8 job su 9 · 1 già in esecuzione, non rilanciato.",
    );
    assert.equal(
      jobsRunAllSummary(summary(6, 2, 2)),
      "Avviati 6 job su 10 · 2 già in esecuzione, non rilanciati · 2 non partiti.",
    );
    assert.equal(jobsRunAllSummary(summary(1, 0, 0)), "Avviato 1 job su 1.");
    assert.equal(jobsRunAllSummary(summary(0, 0, 1)), "Avviati 0 job su 1 · 1 non partito.");
    assert.equal(jobsRunAllTone(summary(9, 0, 0)), "success");
    assert.equal(jobsRunAllTone(summary(8, 1, 0)), "warning");
    assert.equal(jobsRunAllTone(summary(8, 1, 1)), "error");
  });

  it("ultimo giro del job: in esecuzione, riuscito, non riuscito con il motivo", () => {
    assert.equal(jobLastRunLabel(job()), null);
    assert.equal(jobLastRunLabel(job({ running: true })), "In esecuzione");
    assert.equal(
      jobLastRunLabel(job({ lastRun: { outcome: "ok", finishedAt: "2026-11-28T10:00:00Z", reason: null } })),
      "Ultimo giro riuscito",
    );
    assert.equal(
      jobLastRunLabel(
        job({ lastRun: { outcome: "failed", finishedAt: "2026-11-28T10:00:00Z", reason: "Quota finita." } }),
      ),
      "Ultimo giro non riuscito: Quota finita.",
    );
    assert.equal(
      jobLastRunLabel(job({ lastRun: { outcome: "failed", finishedAt: "2026-11-28T10:00:00Z", reason: null } })),
      "Ultimo giro non riuscito",
    );
  });
});

describe("esito per operazione dei Turni", () => {
  it("ok, non riuscita con il messaggio e saltata", () => {
    const ok = turniBatchOperationOutcome({ key: "a", label: "A", status: "ok", message: "Fatto." });
    assert.deepEqual([ok.tone, ok.text], ["success", "Riuscita: Fatto."]);
    const ko = turniBatchOperationOutcome({ key: "a", label: "A", status: "failed", message: "Quota finita." });
    assert.deepEqual([ko.tone, ko.text], ["error", "Non riuscita: Quota finita."]);
    const skipped = turniBatchOperationOutcome({ key: "a", label: "A", status: "skipped", message: null });
    assert.deepEqual([skipped.tone, skipped.text], ["warning", "Saltata"]);
    const waiting = turniBatchOperationOutcome({ key: "a", label: "A", status: "pending", message: null });
    assert.equal(waiting.text, "In attesa");
  });

  it("riepilogo in corso e a fine blocco, con singolare e plurale", () => {
    assert.equal(
      turniBatchSummary(batch({ status: "running", ok: 2, failed: 0, skipped: 0 })),
      "In corso: 2 operazioni su 5 finite.",
    );
    assert.equal(
      turniBatchSummary(batch({ status: "running", ok: 1, failed: 0, skipped: 0 })),
      "In corso: 1 operazione su 5 finite.",
    );
    assert.equal(turniBatchSummary(batch()), "Riuscite 5 operazioni su 5.");
    assert.equal(
      turniBatchSummary(batch({ ok: 3, failed: 1, skipped: 1 })),
      "Riuscite 3 operazioni su 5 · 1 non riuscita · 1 saltata.",
    );
    assert.equal(
      turniBatchSummary(batch({ ok: 1, failed: 4, skipped: 0 })),
      "Riuscita 1 operazione su 5 · 4 non riuscite.",
    );
    assert.equal(
      turniBatchSummary(batch({ ok: 2, failed: 2, skipped: 1 })),
      "Riuscite 2 operazioni su 5 · 2 non riuscite · 1 saltata.",
    );
  });

  it("finito è completed o failed; il tono segue gli errori", () => {
    assert.equal(isTurniBatchFinished(batch()), true);
    assert.equal(isTurniBatchFinished(batch({ status: "failed" })), true);
    assert.equal(isTurniBatchFinished(batch({ status: "running" })), false);
    assert.equal(isTurniBatchFinished(batch({ status: "queued" })), false);
    assert.equal(turniBatchTone(batch()), "success");
    assert.equal(turniBatchTone(batch({ skipped: 1 })), "warning");
    assert.equal(turniBatchTone(batch({ failed: 1 })), "error");
    assert.equal(turniBatchTone(batch({ status: "failed" })), "error");
  });
});
