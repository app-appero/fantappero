import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { avatarInitial, avatarInitials, avatarLetters, firstGrapheme, leadingGraphemes } from "./initials.ts";

/** Esegue `run` come su un motore senza `Intl.Segmenter` (es. Hermes). */
function withoutSegmenter(run: () => void) {
  const intl = Intl as unknown as { Segmenter?: unknown };
  const original = intl.Segmenter;
  delete intl.Segmenter;
  assert.equal(intl.Segmenter, undefined);
  try {
    run();
  } finally {
    intl.Segmenter = original;
  }
}

const ENGINES: Array<[string, (run: () => void) => void]> = [
  ["con Intl.Segmenter", (run) => run()],
  ["senza Intl.Segmenter", withoutSegmenter],
];

for (const [engine, onEngine] of ENGINES) {
  describe(`iniziali degli avatar (${engine})`, () => {
    it("nomi normali: prime due parole, maiuscole", () => {
      onEngine(() => {
        assert.equal(avatarInitials("Mario Rossi"), "MR");
        assert.equal(avatarInitials("  giulia   de rossi "), "GD");
        assert.equal(avatarInitials("Mario De Rossi", { words: "first-last" }), "MR");
        assert.equal(avatarInitials("Leão"), "L");
        assert.equal(avatarInitials("Leão", { singleWordLength: 2 }), "LE");
      });
    });

    it("un'emoji all'inizio resta intera, non «�Ü» (QA 19-20/11)", () => {
      onEngine(() => {
        assert.equal(avatarInitials("😀 Ümit"), "😀Ü");
        assert.equal(avatarInitials("Ümit 😀"), "Ü😀");
        assert.equal(avatarInitial("😀Ümit"), "😀");
        assert.equal(avatarInitials("😀Ümit", { singleWordLength: 2 }), "😀Ü");
      });
    });

    it("prime due lettere del nome, senza spazi (avatar di leghe e squadre)", () => {
      onEngine(() => {
        assert.equal(avatarLetters("Lega Amici"), "LE");
        assert.equal(avatarLetters("A B"), "AB");
        assert.equal(avatarLetters("🔥 Lega"), "🔥L");
        assert.equal(avatarLetters("A🔥"), "A🔥");
        assert.equal(avatarLetters("  "), "?");
        assert.equal(avatarLetters(null), "?");
      });
    });

    it("emoji composte: carnagione, ZWJ, bandiere, variante, keycap", () => {
      onEngine(() => {
        assert.equal(firstGrapheme("👍🏽 Ada"), "👍🏽");
        assert.equal(firstGrapheme("👩‍💻Ada"), "👩‍💻");
        assert.equal(firstGrapheme("👨‍👩‍👧 Famiglia"), "👨‍👩‍👧");
        assert.equal(firstGrapheme("🇮🇹 Italia"), "🇮🇹");
        assert.equal(firstGrapheme("❤️ Cuore"), "❤️");
        assert.equal(firstGrapheme("1️⃣ Uno"), "1️⃣");
        assert.equal(leadingGraphemes("🇮🇹🇧🇷 Calcio", 2), "🇮🇹🇧🇷");
      });
    });

    it("lettere con accento combinante restano una lettera", () => {
      onEngine(() => {
        // «E» + accento acuto combinante (U+0301), come arrivano certi nomi NFD.
        assert.equal(avatarInitial("Émilie"), "É");
        assert.equal(leadingGraphemes("Émilie", 2), "Ém");
      });
    });

    it("nome vuoto: riserva", () => {
      onEngine(() => {
        assert.equal(avatarInitials(""), "?");
        assert.equal(avatarInitials("   "), "?");
        assert.equal(avatarInitials(null, { fallback: "" }), "");
        assert.equal(avatarInitial(undefined), "?");
        assert.equal(avatarInitial("", "—"), "—");
        assert.equal(firstGrapheme(""), "");
        assert.equal(leadingGraphemes("Lega", 0), "");
      });
    });

    it("nessuna iniziale contiene mezza coppia surrogata", () => {
      onEngine(() => {
        for (const name of ["😀 Ümit", "🦁Leoni Uniti", "A😀", "👩‍💻 Ada", "🇮🇹"]) {
          for (const value of [avatarInitials(name), avatarInitial(name), avatarLetters(name), leadingGraphemes(name, 2)]) {
            assert.ok(value.isWellFormed(), `${name} → ${JSON.stringify(value)}`);
          }
        }
      });
    });
  });
}
