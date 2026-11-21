import assert from "node:assert/strict";
import { describe, it } from "node:test";
// L'app usa `getApiErrorMessage` da `@fantappero/api-client`; il file non ha import e si carica dal sorgente.
import { ApiError, getApiErrorMessage } from "../../../../packages/api-client/src/client.ts";
import { submitTrade } from "./tradeSubmit.ts";

const ROUND_IN_PROGRESS = "Mercato e scambi sono chiusi durante il turno in corso: riaprono a calcolo concluso.";

/** Come MarketScreen: il form si chiude e si svuota solo se l'invio è andato. */
async function sendFromForm(send: () => Promise<unknown>) {
  const form = { open: true, offered: ["athlete-1"], error: null as string | null };
  const sent = await submitTrade(send, (error) => {
    form.error = getApiErrorMessage(error, "Impossibile inviare la proposta.");
  });
  if (sent) {
    form.open = false;
    form.offered = [];
  }
  return { sent, form };
}

describe("submitTrade (Nuova proposta, QA 20-21/11)", () => {
  it("con un 400 del server il form resta aperto, compilato e con il messaggio del server", async () => {
    const { sent, form } = await sendFromForm(async () => {
      throw new ApiError(ROUND_IN_PROGRESS, 400, "market_round_in_progress");
    });
    assert.equal(sent, false);
    assert.deepEqual(form, { open: true, offered: ["athlete-1"], error: ROUND_IN_PROGRESS });
  });

  it("senza un messaggio del server resta il testo di riserva, e il form resta aperto", async () => {
    const { sent, form } = await sendFromForm(async () => {
      throw new TypeError("Failed to fetch");
    });
    assert.equal(sent, false);
    assert.equal(form.open, true);
    assert.equal(form.error, "Impossibile inviare la proposta.");
  });

  it("se l'invio va, il form si chiude e si svuota senza errori", async () => {
    const { sent, form } = await sendFromForm(async () => ({ id: "proposal-1" }));
    assert.equal(sent, true);
    assert.deepEqual(form, { open: false, offered: [], error: null });
  });

  it("chiama onError una sola volta e solo in caso di errore", async () => {
    const errors: unknown[] = [];
    const boom = new ApiError("No", 400, "market_closed");
    assert.equal(await submitTrade(async () => undefined, (error) => errors.push(error)), true);
    assert.equal(await submitTrade(async () => Promise.reject(boom), (error) => errors.push(error)), false);
    assert.deepEqual(errors, [boom]);
  });
});
