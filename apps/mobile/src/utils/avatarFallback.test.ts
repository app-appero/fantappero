import assert from "node:assert/strict";
import test from "node:test";
import { visibleAvatarSrc } from "./avatarFallback.ts";

const SRC = "https://api.example/uploads/avatars/qa-02.png";

test("mostra l'immagine finché non è fallita", () => {
  assert.equal(visibleAvatarSrc(SRC, null), SRC);
  assert.equal(visibleAvatarSrc(SRC, undefined), SRC);
});

test("senza immagine si vedono le iniziali", () => {
  for (const value of [null, undefined, ""]) {
    assert.equal(visibleAvatarSrc(value, null), null, JSON.stringify(value));
  }
});

test("un'immagine in errore (es. 404) lascia il posto alle iniziali", () => {
  assert.equal(visibleAvatarSrc(SRC, SRC), null);
});

test("un nuovo indirizzo dopo un errore viene riprovato", () => {
  assert.equal(visibleAvatarSrc(`${SRC}?v=2`, SRC), `${SRC}?v=2`);
});
