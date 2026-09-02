import { describe, expect, it } from "vitest";
import { CreateLeagueScreen } from "./CreateLeagueScreen";

describe("EP03-01 CreateLeagueScreen", () => {
  it("exports create league screen component", () => {
    expect(typeof CreateLeagueScreen).toBe("function");
  });
});
