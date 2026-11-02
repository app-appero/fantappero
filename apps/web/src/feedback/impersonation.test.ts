import { describe, expect, it } from "vitest";
import { impersonationDestination } from "./impersonation";

describe("impersonationDestination", () => {
  it("porta sulla pagina in cui è comparso il problema", () => {
    expect(impersonationDestination("/lega/amministrazione")).toBe("/lega/amministrazione");
    expect(impersonationDestination("/formazione?turno=3")).toBe("/formazione?turno=3");
  });

  it("ripiega sulle leghe se il contesto manca o non è un percorso interno", () => {
    for (const value of [null, undefined, "", "Formation", "https://evil.example", "//evil.example", "/\\evil"]) {
      expect(impersonationDestination(value)).toBe("/leghe");
    }
  });

  it("non porta mai in aree operatore, accesso o nella pagina di segnalazione", () => {
    for (const value of ["/admin", "/admin/utenti", "/accedi", "/feedback"]) {
      expect(impersonationDestination(value)).toBe("/leghe");
    }
  });
});
