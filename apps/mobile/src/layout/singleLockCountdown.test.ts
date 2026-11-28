import assert from "node:assert/strict";
import { readFileSync, readdirSync } from "node:fs";
import { join, relative } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, it } from "node:test";

// 28/11, decisione di Rosario: una sola riga «Prossimo blocco». Nell'app è la fascia sotto
// l'intestazione (`LockCountdownBar`, testID `header-lock-strip`): prima Formazione e Turni
// ne avevano una seconda sotto il titolo, con lo stesso dato. Resta invece il testo di stato
// senza conto alla rovescia («Turno non ancora aperto», «Turno saltato», «Formazione
// confermata»…): la regola è in `showsPageLockNote` (provata in `pageLockNote.test.ts`) e qui
// si controlla che le due schermate la usino. L'app non ha un renderer nei test: si legge il
// sorgente, come per le altre regole di disposizione.

const SRC = fileURLToPath(new URL("..", import.meta.url));

function source(path: string): string {
  return readFileSync(join(SRC, path), "utf8");
}

function sourceFiles(dir: string): string[] {
  return (readdirSync(join(SRC, dir), { recursive: true, encoding: "utf8" }) as string[])
    .filter((name) => /\.tsx?$/.test(name) && !/\.test\.tsx?$/.test(name))
    .map((name) => join(dir, name));
}

describe("Una sola riga «Prossimo blocco» nell'app: la fascia sotto l'intestazione (28/11)", () => {
  it("solo Formazione e Turni montano il componente, e solo dove non c'è il conto alla rovescia", () => {
    const users = sourceFiles("screens").filter((path) => {
      const text = source(path);
      return (
        /components\/LockCountdown["']/.test(text) ||
        /<LockCountdown\b/.test(text) ||
        /useLockCountdown\b/.test(text) ||
        /[>"'`]Prossimo blocco[<"'`]/.test(text)
      );
    });
    assert.deepEqual(users.map((path) => relative("screens", path)).sort(), [
      "FormationScreen.tsx",
      "MatchdayScreen.tsx",
    ]);

    const formation = source("screens/FormationScreen.tsx");
    const matchday = source("screens/MatchdayScreen.tsx");
    // Un solo punto in cui la schermata monta il testo, dietro la regola (mai con il conto in corso).
    assert.equal((formation.match(/<LockCountdown\b/g) ?? []).length, 1);
    assert.equal((matchday.match(/<LockCountdown\b/g) ?? []).length, 1);
    assert.match(
      formation,
      /\{countdown && showsPageLockNote\(countdown, context\.roundId\) \? \(\n\s*<LockCountdown/,
    );
    assert.match(
      matchday,
      /\{countdown && showsPageLockNote\(countdown, selected\.id\) \? \(\n\s*<LockCountdown/,
    );
    assert.doesNotMatch(formation, /countdown\.roundId === context\.roundId \? \(/);
    assert.doesNotMatch(matchday, /countdown\.roundId === selected\.id \? \(/);
  });

  it("il conto alla rovescia lo monta solo la fascia (barra normale e barra con le mosse)", () => {
    const users = sourceFiles(".")
      .filter((path) => /components\/LockCountdown["']/.test(source(path)))
      .map((path) => path.replace(/\\/g, "/"))
      .sort();
    assert.deepEqual(users, [
      "layout/LockCountdownBar.tsx",
      "screens/FormationScreen.tsx",
      "screens/MatchdayScreen.tsx",
    ]);

    const bar = source("layout/LockCountdownBar.tsx");
    // Barra normale e barra «agganciata» sono la stessa fascia (stesso testID), mai insieme.
    assert.equal((bar.match(/testID="header-lock-strip"/g) ?? []).length, 2);
    assert.match(bar, /if \(dock\) \{\n\s*return \(/);
  });

  it("la fascia sta sopra Turni e Formazione, e sopra le schermate fuori dal menù (dettaglio Partita e Scontro)", () => {
    const tabs = source("navigation/AppTabNavigator.tsx");
    assert.equal((tabs.match(/<LockCountdownBar \/>/g) ?? []).length, 1);
    assert.match(tabs, /Matchday: MatchdayScreen,/);
    assert.match(tabs, /Formation: FormationScreen,/);
    // La fascia sta nella struttura che contiene tutte le schede, non dentro una scheda sola.
    assert.ok(tabs.indexOf("<LockCountdownBar />") < tabs.indexOf("<Tab.Navigator"));

    const root = source("navigation/RootNavigator.tsx");
    assert.match(root, /FixtureDetailWithCountdown = withLockCountdown\(FixtureDetailScreen\)/);
    assert.match(root, /MatchupDetailWithCountdown = withLockCountdown\(MatchupDetailScreen\)/);
  });

  it("Formazione tiene «Mosse usate N/M» al suo posto, e scorrendo la fascia si unisce alle mosse", () => {
    const formation = source("screens/FormationScreen.tsx");
    assert.match(formation, /Mosse usate \{movesUsed\}\/\{maxMoves\}/);
    assert.match(formation, /testID="formation-moves"/);
    assert.match(formation, /setMovesDock\(scrolledPast && isFocused \? \{ used: movesUsed, max: maxMoves, draft: draftMove \} : null\)/);
    const bar = source("layout/LockCountdownBar.tsx");
    assert.match(bar, /Mosse \{dock\.used\}\/\{dock\.max\}/);
  });
});
