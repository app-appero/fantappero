import { describe, expect, it } from "vitest";
import { APP_ROUTE_DEFINITIONS, ROOT_ALIASES } from "./routeConfig";

describe("routeConfig (EPUI-05)", () => {
  it("registers all member and admin placeholder routes", () => {
    const paths = APP_ROUTE_DEFINITIONS.map((route) => route.path);
    expect(paths).toContain("/leghe");
    expect(paths).toContain("/leghe/invito");
    expect(paths).toContain("/lega/home");
    expect(paths).toContain("/turni");
    expect(paths).toContain("/classifica");
    expect(paths).toContain("/admin");
    expect(paths).toContain("/accedi");
  });

  it("uses unique route ids and paths", () => {
    const ids = APP_ROUTE_DEFINITIONS.map((route) => route.id);
    const paths = APP_ROUTE_DEFINITIONS.map((route) => route.path);
    expect(new Set(ids).size).toBe(ids.length);
    expect(new Set(paths).size).toBe(paths.length);
  });

  it("assigns admin layout only to global operator routes", () => {
    const adminRoutes = APP_ROUTE_DEFINITIONS.filter((route) => route.layout === "admin");
    expect(adminRoutes.every((route) => route.requireGlobalOperator)).toBe(true);
    expect(adminRoutes.every((route) => route.path.startsWith("/admin"))).toBe(true);
  });

  it("documents root aliases handled by the router", () => {
    expect(ROOT_ALIASES).toContain("/");
  });
});
