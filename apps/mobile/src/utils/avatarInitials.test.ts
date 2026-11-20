import assert from "node:assert/strict";
import { describe, it } from "node:test";
// L'app usa questi helper da `@fantappero/contracts`; il file non ha import e si carica dal sorgente.
import {
  avatarInitial,
  avatarInitials,
  avatarLetters,
  firstGrapheme,
} from "../../../../packages/contracts/src/initials.ts";

/** Hermes non sempre ha `Intl.Segmenter`: le iniziali devono restare intere anche senza. */
function onHermesLikeEngine(run: () => void) {
  const intl = Intl as unknown as { Segmenter?: unknown };
  const original = intl.Segmenter;
  delete intl.Segmenter;
  try {
    run();
  } finally {
    intl.Segmenter = original;
  }
}

describe("iniziali degli avatar nell'app (QA 19-20/11)", () => {
  it("TeamAvatar e utenti admin: prime due parole, emoji intera", () => {
    onHermesLikeEngine(() => {
      assert.equal(avatarInitials("Giulia Rossi"), "GR");
      assert.equal(avatarInitials("😀 Ümit Kaya"), "😀Ü");
      assert.equal(avatarInitials("👩‍💻 Ada"), "👩‍💻A");
    });
  });

  it("scheda calciatore: prima e ultima parola, due lettere con un nome solo", () => {
    onHermesLikeEngine(() => {
      assert.equal(avatarInitials("Lautaro Javier Martínez", { words: "first-last", singleWordLength: 2 }), "LM");
      assert.equal(avatarInitials("Leão", { words: "first-last", singleWordLength: 2 }), "LE");
    });
  });

  it("profilo, allenatori, asta live, formazione: una sola iniziale", () => {
    onHermesLikeEngine(() => {
      assert.equal(avatarInitial("😀Ümit"), "😀");
      assert.equal(avatarInitial("  marco"), "M");
      assert.equal(avatarInitial(null), "?");
    });
  });

  it("selettore lega, crediti e scambi: prime due lettere senza spezzare l'emoji", () => {
    onHermesLikeEngine(() => {
      assert.equal(avatarLetters("Lega Amici"), "LE");
      assert.equal(avatarLetters("A🔥 Team"), "A🔥");
      assert.equal(avatarLetters("🇮🇹 Azzurri"), "🇮🇹A");
    });
  });

  it("campo: iniziale del nome puntata", () => {
    onHermesLikeEngine(() => {
      assert.equal(`${firstGrapheme("Émile")}.`, "É.");
      assert.equal(`${firstGrapheme("😀Ümit")}.`, "😀.");
    });
  });
});
