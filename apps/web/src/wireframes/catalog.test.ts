import { describe, expect, it } from "vitest";
import {
  ALL_MACROFLOWS,
  WIREFRAME_CATALOG,
  WIREFRAME_STATES,
  macroflowsCovered,
} from "./catalog";

describe("wireframe catalog (EPUI-04)", () => {
  it("defines 10 wireframe screens covering all 11 UI areas", () => {
    expect(WIREFRAME_CATALOG.length).toBe(10);
    const routes = WIREFRAME_CATALOG.map((s) => s.route);
    expect(routes).toContain("/accedi");
    expect(routes).toContain("/classifica");
    expect(routes).toContain("/asta");
    expect(routes).toContain("/formazione");
  });

  it("covers all macroflows M1–M4", () => {
    const covered = macroflowsCovered();
    for (const flow of ALL_MACROFLOWS) {
      expect(covered.has(flow)).toBe(true);
    }
  });

  it("defines non-empty flow metadata for every screen", () => {
    for (const screen of WIREFRAME_CATALOG) {
      expect(screen.primaryCta.trim().length).toBeGreaterThan(0);
      expect(screen.priorityInfo.length).toBeGreaterThan(0);
      expect(screen.criticalSteps.length).toBeGreaterThan(0);
      expect(screen.roles.length).toBeGreaterThan(0);
    }
  });

  it("defines all five UI states in catalog messages", () => {
    for (const screen of WIREFRAME_CATALOG) {
      expect(screen.loading.title).toBeTruthy();
      expect(screen.empty.title).toBeTruthy();
      expect(screen.error.title).toBeTruthy();
      expect(screen.forbidden.title).toBeTruthy();
    }
    expect(WIREFRAME_STATES).toEqual(["loading", "empty", "error", "success", "forbidden"]);
  });
});
