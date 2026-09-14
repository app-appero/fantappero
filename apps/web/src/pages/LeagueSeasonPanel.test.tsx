import { describe, expect, it } from "vitest";
import { hrefForLifecycleAction } from "./LeagueSeasonPanel";

describe("hrefForLifecycleAction", () => {
  it("porta le rose su Mercato → Rosa, non in Amministrazione", () => {
    expect(hrefForLifecycleAction("teams")).toBe("/rosa");
  });

  it("porta il calendario sui Turni", () => {
    expect(hrefForLifecycleAction("calendar")).toBe("/turni?tab=calendario");
  });

  it("lascia regolamento e partecipanti nella pagina di setup", () => {
    expect(hrefForLifecycleAction("rules")).toBeNull();
    expect(hrefForLifecycleAction("members")).toBeNull();
  });
});
