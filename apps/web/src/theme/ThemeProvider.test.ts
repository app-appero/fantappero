import { describe, expect, it } from "vitest";
import { applyDocumentTheme, resolveSurface } from "./ThemeProvider";

describe("resolveSurface (EPUI-05)", () => {
  it("maps member routes to app surface", () => {
    expect(resolveSurface("/leghe")).toBe("app");
    expect(resolveSurface("/turni")).toBe("app");
  });

  it("maps admin routes to admin surface", () => {
    expect(resolveSurface("/admin")).toBe("admin");
    expect(resolveSurface("/admin/leghe")).toBe("admin");
  });

  it("maps auth routes to auth surface", () => {
    expect(resolveSurface("/accedi")).toBe("auth");
    expect(resolveSurface("/accedi/registrati")).toBe("auth");
  });
});

describe("applyDocumentTheme (EPUI-05)", () => {
  it("sets lang, theme and surface on the document", () => {
    applyDocumentTheme("fantappero", "admin");
    expect(document.documentElement.lang).toBe("it");
    expect(document.documentElement.dataset.theme).toBe("fantappero");
    expect(document.body.dataset.surface).toBe("admin");
  });
});
