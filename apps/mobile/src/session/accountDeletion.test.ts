import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { describe, it } from "node:test";
import { deleteAccountAndForget } from "./accountDeletion.ts";

function recorder(options: { deleteFails?: boolean } = {}) {
  const calls: string[] = [];
  return {
    calls,
    steps: {
      deleteAccount: async () => {
        calls.push("delete");
        if (options.deleteFails) {
          throw new Error("Password non corretta.");
        }
      },
      forgetLastUser: async () => {
        calls.push("forget");
      },
      logout: async () => {
        calls.push("logout");
      },
    },
  };
}

describe("eliminazione dell'account e ultimo accesso (corsa M1, 22/11)", () => {
  it("dopo l'eliminazione dimentica l'ultimo accesso prima di uscire", async () => {
    const { calls, steps } = recorder();
    await deleteAccountAndForget(steps);
    // L'accesso si apre dopo il logout: l'ultimo utente deve essere già cancellato.
    assert.deepEqual(calls, ["delete", "forget", "logout"]);
  });

  it("se l'eliminazione fallisce l'ultimo accesso resta e non si esce", async () => {
    const { calls, steps } = recorder({ deleteFails: true });
    await assert.rejects(deleteAccountAndForget(steps), /Password non corretta/);
    assert.deepEqual(calls, ["delete"]);
  });

  it("il Profilo passa da qui con clearLastUser", () => {
    const source = readFileSync(new URL("../screens/ProfileScreen.tsx", import.meta.url), "utf8");
    assert.match(source, /deleteAccountAndForget\(\{/);
    assert.match(source, /forgetLastUser: clearLastUser/);
  });
});
