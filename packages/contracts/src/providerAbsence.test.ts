import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { absenceKindLabel, absenceLine, italianAbsenceText } from "./providerAbsence.ts";

describe("rientro in italiano (Rosario 27/11)", () => {
  it("i casi dello schermo «Partita»", () => {
    assert.equal(italianAbsenceText("Mid December 2026"), "metà dicembre 2026");
    assert.equal(italianAbsenceText("Early December 2026"), "inizio dicembre 2026");
    assert.equal(italianAbsenceText("Early January 2027"), "inizio gennaio 2027");
    assert.equal(italianAbsenceText("Late February 2027"), "fine febbraio 2027");
  });

  it("tutti i mesi e le abbreviazioni", () => {
    const months: Array<[string, string]> = [
      ["January", "gennaio"],
      ["February", "febbraio"],
      ["March", "marzo"],
      ["April", "aprile"],
      ["May", "maggio"],
      ["June", "giugno"],
      ["July", "luglio"],
      ["August", "agosto"],
      ["September", "settembre"],
      ["October", "ottobre"],
      ["November", "novembre"],
      ["December", "dicembre"],
    ];
    for (const [english, italian] of months) {
      assert.equal(italianAbsenceText(`Mid ${english} 2027`), `metà ${italian} 2027`);
      assert.equal(italianAbsenceText(`${english} 2027`), `${italian} 2027`);
      assert.equal(italianAbsenceText(`late ${english.slice(0, 3)} 2027`), `fine ${italian} 2027`);
    }
    assert.equal(italianAbsenceText("Sept 2027"), "settembre 2027");
  });

  it("senza anno, con maiuscole e trattini diversi", () => {
    assert.equal(italianAbsenceText("Mid-December"), "metà dicembre");
    assert.equal(italianAbsenceText("EARLY JANUARY"), "inizio gennaio");
    assert.equal(italianAbsenceText("  late   March 2027  "), "fine marzo 2027");
    assert.equal(italianAbsenceText("End of May 2027"), "fine maggio 2027");
    assert.equal(italianAbsenceText("Beginning of April"), "inizio aprile");
    assert.equal(italianAbsenceText("Early 2027"), "inizio 2027");
  });

  it("le date precise restano precise", () => {
    assert.equal(italianAbsenceText("2026-12-12"), "12/12/2026");
    assert.equal(italianAbsenceText("2026-12-05T00:00:00Z"), "05/12/2026");
    assert.equal(italianAbsenceText("12 Dec 2026"), "12 dicembre 2026");
    assert.equal(italianAbsenceText("1st January 2027"), "1 gennaio 2027");
    assert.equal(italianAbsenceText("Dec 12, 2026"), "12 dicembre 2026");
    assert.equal(italianAbsenceText("March 3rd"), "3 marzo");
    // Già in numeri all'italiana: non si tocca.
    assert.equal(italianAbsenceText("12/12/2026"), "12/12/2026");
    // Data impossibile: resta com'è.
    assert.equal(italianAbsenceText("2026-13-45"), "2026-13-45");
  });

  it("durate: giorni, settimane, mesi", () => {
    assert.equal(italianAbsenceText("1 week"), "1 settimana");
    assert.equal(italianAbsenceText("3 weeks"), "3 settimane");
    assert.equal(italianAbsenceText("2-3 weeks"), "2-3 settimane");
    assert.equal(italianAbsenceText("2 to 3 months"), "2-3 mesi");
    assert.equal(italianAbsenceText("Around 4 months"), "circa 4 mesi");
    assert.equal(italianAbsenceText("1 day"), "1 giorno");
    assert.equal(italianAbsenceText("A few weeks"), "qualche settimana");
    assert.equal(italianAbsenceText("a few days"), "qualche giorno");
    assert.equal(italianAbsenceText("Back in training"), "di nuovo in allenamento");
  });
});

describe("stato in italiano", () => {
  it("«Doubtful» e gli altri stati del fornitore", () => {
    assert.equal(italianAbsenceText("Doubtful"), "Dubbio");
    assert.equal(italianAbsenceText("doubtful"), "Dubbio");
    assert.equal(italianAbsenceText("Questionable"), "Dubbio");
    assert.equal(italianAbsenceText("Out"), "Fuori");
    assert.equal(italianAbsenceText("Ruled out"), "Fuori");
    assert.equal(italianAbsenceText("Suspended"), "Squalificato");
    assert.equal(italianAbsenceText("Suspension"), "Squalificato");
    assert.equal(italianAbsenceText("Injured"), "Infortunato");
    assert.equal(italianAbsenceText("Red card"), "Espulso");
    assert.equal(italianAbsenceText("Day to day"), "Giorno per giorno");
    assert.equal(italianAbsenceText("Day-to-day"), "Giorno per giorno");
    assert.equal(italianAbsenceText("Unknown"), "rientro non noto");
    assert.equal(italianAbsenceText("Missing Fixture"), "Assente");
    assert.equal(italianAbsenceText("Illness"), "Malattia");
    assert.equal(italianAbsenceText("Personal reasons"), "Motivi personali");
  });

  it("più parti insieme si traducono una per una", () => {
    assert.equal(italianAbsenceText("Doubtful, Mid December 2026"), "Dubbio, metà dicembre 2026");
    assert.equal(italianAbsenceText("Out - Late February 2027"), "Fuori, fine febbraio 2027");
    // Una parte che non si riconosce resta com'è.
    assert.equal(italianAbsenceText("Hamstring, Early March"), "Hamstring, inizio marzo");
  });
});

describe("testi che non si toccano", () => {
  it("vuoto o mancante è nulla", () => {
    assert.equal(italianAbsenceText(null), null);
    assert.equal(italianAbsenceText(undefined), null);
    assert.equal(italianAbsenceText(""), null);
    assert.equal(italianAbsenceText("   "), null);
  });

  it("il testo già in italiano o sconosciuto resta com'è", () => {
    assert.equal(italianAbsenceText("Dubbio"), "Dubbio");
    assert.equal(italianAbsenceText("Squalificato"), "Squalificato");
    assert.equal(italianAbsenceText("metà dicembre 2026"), "metà dicembre 2026");
    assert.equal(italianAbsenceText("Hamstring injury"), "Hamstring injury");
  });

  it("tradurre due volte dà lo stesso testo", () => {
    for (const text of ["Mid December 2026", "Doubtful", "2026-12-12", "3 weeks", "Day to day"]) {
      const once = italianAbsenceText(text);
      assert.equal(italianAbsenceText(once), once);
    }
  });
});

describe("tipo di assenza", () => {
  it("i tipi che manda il server", () => {
    assert.equal(absenceKindLabel("injury"), "Infortunio");
    assert.equal(absenceKindLabel("Injury"), "Infortunio");
    assert.equal(absenceKindLabel("suspension"), "Squalifica");
    assert.equal(absenceKindLabel("suspended"), "Squalifica");
    assert.equal(absenceKindLabel("red_card"), "Espulsione");
    assert.equal(absenceKindLabel("red"), "Espulsione");
    assert.equal(absenceKindLabel("Doubtful"), "Dubbio");
    assert.equal(absenceKindLabel("Questionable"), "Dubbio");
    assert.equal(absenceKindLabel("Out"), "Fuori");
  });

  it("senza tipo noto è «Indisponibile»", () => {
    assert.equal(absenceKindLabel(null), "Indisponibile");
    assert.equal(absenceKindLabel(""), "Indisponibile");
    assert.equal(absenceKindLabel("qualcosa di nuovo"), "Indisponibile");
  });
});

describe("riga «Infortunati e squalificati»", () => {
  it("tipo e rientro in italiano, separati da un punto", () => {
    assert.equal(absenceLine("injury", "Mid December 2026"), "Infortunio · metà dicembre 2026");
    assert.equal(absenceLine("injury", "Early January 2027"), "Infortunio · inizio gennaio 2027");
    assert.equal(absenceLine("injury", "Doubtful"), "Infortunio · Dubbio");
    assert.equal(absenceLine("suspension", "Late February 2027"), "Squalifica · fine febbraio 2027");
    assert.equal(absenceLine("injury", "Unknown"), "Infortunio · rientro non noto");
  });

  it("senza testo resta il solo tipo", () => {
    assert.equal(absenceLine("injury", null), "Infortunio");
    assert.equal(absenceLine("suspension", ""), "Squalifica");
    assert.equal(absenceLine(null, null), "Indisponibile");
    assert.equal(absenceLine(null, "Mid December 2026"), "Indisponibile · metà dicembre 2026");
  });

  it("tipo e testo uguali non si ripetono", () => {
    assert.equal(absenceLine("Doubtful", "Doubtful"), "Dubbio");
    assert.equal(absenceLine("doubtful", "Mid December 2026"), "Dubbio · metà dicembre 2026");
  });

  it("nessun testo inglese del fornitore resta nella riga", () => {
    const samples = [
      "Mid December 2026",
      "Early December 2026",
      "Early January 2027",
      "Late February 2027",
      "Doubtful",
      "Questionable",
      "Out",
      "Suspended",
      "Day to day",
      "Unknown",
    ];
    for (const sample of samples) {
      const line = absenceLine("injury", sample);
      assert.doesNotMatch(
        line,
        /\b(mid|early|late|december|january|february|doubtful|questionable|out|suspended|day to day|unknown)\b/i,
        `${sample} → ${line}`,
      );
    }
  });
});
