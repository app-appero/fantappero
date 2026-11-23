import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { describe, it } from "node:test";
import {
  requestLeagueListRefresh,
  sameLeagueList,
  subscribeLeagueListRefresh,
} from "./leagueListRefresh.ts";

const lega = (id: string, extra: Partial<{ name: string; state: "active" | "draft"; marketOpen: boolean }> = {}) => ({
  id,
  name: extra.name ?? `Lega ${id}`,
  role: "member" as const,
  state: extra.state ?? ("active" as const),
  marketOpen: extra.marketOpen ?? true,
});

const read = (path: string) => readFileSync(new URL(path, import.meta.url), "utf8");

describe("selettore leghe: una lega creata fuori dall'app compare senza riavvio (corsa M3, 22/11)", () => {
  it("la richiesta di aggiornamento arriva a chi ascolta, finché ascolta", () => {
    let seen = 0;
    const unsubscribe = subscribeLeagueListRefresh(() => {
      seen += 1;
    });
    requestLeagueListRefresh();
    unsubscribe();
    requestLeagueListRefresh();
    assert.equal(seen, 1);
  });

  it("una lega nuova (creata dal sito) è un elenco diverso", () => {
    assert.equal(sameLeagueList([lega("a")], [lega("a"), lega("b")]), false);
    assert.equal(sameLeagueList([], [lega("b")]), false);
  });

  it("nome, stato o mercato cambiati sono un elenco diverso", () => {
    assert.equal(sameLeagueList([lega("a")], [lega("a", { name: "Nuovo nome" })]), false);
    assert.equal(sameLeagueList([lega("a")], [lega("a", { state: "draft" })]), false);
    assert.equal(sameLeagueList([lega("a")], [lega("a", { marketOpen: false })]), false);
  });

  it("lo stesso elenco riletto non cambia nulla", () => {
    assert.equal(sameLeagueList([lega("a"), lega("b")], [lega("a"), lega("b")]), true);
    assert.equal(sameLeagueList([], []), true);
  });

  it("ogni «tira per aggiornare» chiede l'elenco e la sessione lo rilegge, anche al ritorno nell'app", () => {
    const page = read("../layout/PageContainer.tsx");
    assert.match(page, /onRefresh=\{\(\) => \{\n(?:\s*\/\/.*\n)?\s*requestLeagueListRefresh\(\);\n\s*void onRefresh\(\);/);
    const session = read("./DemoSessionContext.tsx");
    assert.match(session, /subscribeLeagueListRefresh\(refresh\)/);
    assert.match(session, /if \(state === "active"\) \{\n\s*refresh\(\);/);
    assert.match(session, /setLeagues\(\(current\) => \(sameLeagueList\(current, memberships\) \? current : memberships\)\)/);
  });
});
