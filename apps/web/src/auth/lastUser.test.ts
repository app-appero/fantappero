import { describe, expect, it } from "vitest";
import { initialsOf } from "./lastUser";

describe("initialsOf (avatar dell'ultimo accesso)", () => {
  it("prende la prima e l'ultima parola", () => {
    expect(initialsOf("Mario De Rossi")).toBe("MR");
    expect(initialsOf("giulia")).toBe("G");
  });

  it("un'emoji all'inizio resta intera, non mezza coppia surrogata (QA 19-20/11)", () => {
    expect(initialsOf("😀 Ümit")).toBe("😀Ü");
    expect(initialsOf("Ümit 😀")).toBe("Ü😀");
    expect(initialsOf("👍🏽 Ada Lovelace")).toBe("👍🏽L");
  });

  it("senza nome mostra un punto interrogativo", () => {
    expect(initialsOf("   ")).toBe("?");
  });
});
