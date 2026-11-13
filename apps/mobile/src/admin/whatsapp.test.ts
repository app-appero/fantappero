import assert from "node:assert/strict";
import test from "node:test";

import { whatsappUrl } from "./whatsapp.ts";

test("whatsappUrl aggiunge il prefisso italiano ai numeri senza prefisso", () => {
  assert.equal(whatsappUrl("333 123 4567"), "https://wa.me/393331234567");
});

test("whatsappUrl rispetta il prefisso internazionale (+ o 00)", () => {
  assert.equal(whatsappUrl("+39 333 1234567"), "https://wa.me/393331234567");
  assert.equal(whatsappUrl("0044 7700 900123"), "https://wa.me/447700900123");
});
