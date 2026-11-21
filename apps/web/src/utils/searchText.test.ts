import { describe, expect, it } from "vitest";
import { foldSearchText, matchesSearch, repairMojibake } from "./searchText";

describe("repairMojibake (QA 20-21/11)", () => {
  it("repairs UTF-8 read as Latin-1 or Windows-1252, even twice", () => {
    expect(repairMojibake("L. JovanoviÄ\u0087")).toBe("L. Jovanović");
    expect(repairMojibake("R. ObriÄ\u0087")).toBe("R. Obrić");
    expect(repairMojibake("D. PejiÄ\u008diÄ\u0087")).toBe("D. Pejičić");
    expect(repairMojibake("N. KovaÄ\u008d")).toBe("N. Kovač");
    expect(repairMojibake("L. JovanoviÄ‡")).toBe("L. Jovanović");
    expect(repairMojibake("A. DembÃƒÂ©lÃƒÂ©")).toBe("A. Dembélé");
    expect(repairMojibake("Y. Nâ€™Dicka")).toBe("Y. N’Dicka");
  });

  it("leaves correct names unchanged", () => {
    for (const name of [
      "A. Dembélé",
      "H. Bellerín",
      "A. Bayındır",
      "E. İlkhan",
      "Š. Vrsaljko",
      "Ž. Ivanušec",
      "M. Ødegaard",
      "Ç. Söyüncü",
      "João Mário",
      "N’Dicka",
      "Nicolò Barella",
      "Ã Test",
      "",
    ]) {
      expect(repairMojibake(name)).toBe(name);
    }
    // Decodifica a un controllo (U+0085): resta com'è.
    expect(repairMojibake("AÂ\u0085B")).toBe("AÂ\u0085B");
  });
});

describe("foldSearchText / matchesSearch", () => {
  it("finds names with broken encoding without accents", () => {
    expect(matchesSearch("L. JovanoviÄ\u0087 Udinese", "jovanovic")).toBe(true);
    expect(matchesSearch("R. ObriÄ\u0087", "Obrić")).toBe(true);
    expect(matchesSearch("N. KovaÄ\u008d", "kovac")).toBe(true);
    expect(foldSearchText("A. DembÃ©lÃ©")).toBe("a. dembele");
  });

  it("still folds correct accented names", () => {
    expect(foldSearchText("  Çalhanoğlu ")).toBe("calhanoglu");
    expect(matchesSearch("A. Bayındır", "bayindir")).toBe(true);
    expect(matchesSearch("A. Dembélé", "jovanovic")).toBe(false);
  });
});
