import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { describe, it } from "node:test";

type HookOrder = {
  /** Righe (1-based) degli hook chiamati nel corpo del componente. */
  hooks: number[];
  /** Righe (1-based) degli `if (…) { return … }` nel corpo del componente. */
  earlyReturns: number[];
  /** Hook che vengono dopo il primo return anticipato: devono essere zero. */
  hooksAfterEarlyReturn: string[];
};

const HOOK_CALL = /^ {2}(?! )(?:.*\W)?use[A-Z]\w*\s*(?:<.*>)?\(/;

/**
 * Hook e return anticipati di primo livello di `export function <component>()`, letti dal
 * sorgente indentato a due spazi come il resto dell'app. Un hook dopo un return anticipato
 * cambia il numero di hook tra un render e l'altro (React #300, «Qualcosa è andato storto»).
 */
function hookOrder(source: string, component: string): HookOrder {
  const lines = source.split("\n");
  const start = lines.findIndex((line) => line.startsWith(`export function ${component}(`));
  assert.ok(start >= 0, `manca export function ${component}`);
  const end = lines.findIndex((line, index) => index > start && line === "}");
  assert.ok(end > start, `corpo di ${component} non chiuso`);

  const hooks: number[] = [];
  const earlyReturns: number[] = [];
  for (let index = start + 1; index < end; index += 1) {
    const line = lines[index] ?? "";
    if (/^ {2}(?:\/\/|\/\*|\*)/.test(line)) {
      continue;
    }
    if (HOOK_CALL.test(line)) {
      hooks.push(index + 1);
      continue;
    }
    if (/^ {2}if \(/.test(line)) {
      for (let inner = index + 1; inner < end; inner += 1) {
        const innerLine = lines[inner] ?? "";
        if (/^ {2}\}/.test(innerLine)) {
          break;
        }
        if (/^ {4}return\b/.test(innerLine)) {
          earlyReturns.push(index + 1);
          break;
        }
      }
    }
  }
  const firstReturn = earlyReturns[0] ?? Number.POSITIVE_INFINITY;
  const hooksAfterEarlyReturn = hooks
    .filter((line) => line > firstReturn)
    .map((line) => `${component}:${line} ${(lines[line - 1] ?? "").trim()}`);
  return { hooks, earlyReturns, hooksAfterEarlyReturn };
}

const readScreen = (name: string) => readFileSync(new URL(`./${name}`, import.meta.url), "utf8");

describe("hook prima dei return anticipati (QA 22→23/11)", () => {
  it("riconosce un hook dopo un return anticipato", () => {
    const source = [
      "export function Demo() {",
      "  const [a, setA] = useState(0);",
      "  if (!ok) {",
      "    return null;",
      "  }",
      "  const [b, setB] = useState<string | null>(null);",
      "  useEffect(() => {",
      "  }, []);",
      "  return <View />;",
      "}",
    ].join("\n");
    const order = hookOrder(source, "Demo");
    assert.deepEqual(order.earlyReturns, [3]);
    assert.deepEqual(order.hooks, [2, 6, 7]);
    assert.equal(order.hooksAfterEarlyReturn.length, 2);
  });

  it("Amministrazione lega: dopo «Elimina lega» il permesso cade e gli hook restano gli stessi", () => {
    const order = hookOrder(readScreen("LeagueAdminScreen.tsx"), "LeagueAdminScreen");
    // Il return di «Permessi insufficienti» c'è e gli hook sono stati letti davvero.
    assert.ok(order.earlyReturns.length >= 1, "manca il return di «Permessi insufficienti»");
    assert.ok(order.hooks.length >= 40, `hook letti: ${order.hooks.length}`);
    assert.deepEqual(order.hooksAfterEarlyReturn, []);
  });

  it("Fantallenatori: nessun hook dopo «Permessi insufficienti»", () => {
    const order = hookOrder(readScreen("ManagerDirectoryScreen.tsx"), "ManagerDirectoryScreen");
    assert.ok(order.earlyReturns.length >= 1, "manca il return di «Permessi insufficienti»");
    assert.ok(order.hooks.length >= 5, `hook letti: ${order.hooks.length}`);
    assert.deepEqual(order.hooksAfterEarlyReturn, []);
  });
});
