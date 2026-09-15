import { describe, expect, it } from "vitest";
import {
  clearStoredSession,
  loadStoredMyLeagues,
  saveStoredMyLeagues,
  saveStoredSession,
} from "./sessionStorage";

const USER = { id: "user-1", displayName: "Romy", globalRole: "global_operator" as const };

const LEAGUE = {
  id: "lega-test",
  name: "Lega di test",
  role: "league_admin" as const,
  state: "draft" as const,
};

describe("sessionStorage membership cache", () => {
  it("returns cached leagues only for the same user", () => {
    saveStoredMyLeagues(USER.id, [LEAGUE]);
    expect(loadStoredMyLeagues(USER.id)).toEqual([LEAGUE]);
    expect(loadStoredMyLeagues("altro-utente")).toEqual([]);
  });

  it("clears cached leagues with the session", () => {
    saveStoredSession({
      accessToken: "a",
      refreshToken: "r",
      user: USER,
    });
    saveStoredMyLeagues(USER.id, [LEAGUE]);
    clearStoredSession();
    expect(loadStoredMyLeagues(USER.id)).toEqual([]);
  });
});
